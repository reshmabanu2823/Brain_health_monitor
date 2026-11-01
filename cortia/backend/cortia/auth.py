import hashlib
import secrets
import time
from collections import defaultdict, deque
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from .models import User, AuthToken

router = APIRouter(prefix='/api/auth', tags=['Authentication'])
passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = passwords.hash('constant-non-account-verification-password')

def get_db(request: Request):
    with request.app.state.db() as db:
        yield db

def resolve_user(db, token):
    if not token:
        return None
    record = db.get(AuthToken, hashlib.sha256(token.encode()).hexdigest())
    if record is None or record.expires < time.time():
        return None
    return db.get(User, record.user_id)

def current_user(request: Request, db=Depends(get_db)):
    user = resolve_user(db, request.cookies.get('cortia_session'))
    if user is None:
        raise HTTPException(401, 'Sign in required')
    return user

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=128)


def public(user):
    return dict(id=user.id, username=user.username, created_at=user.created_at)


def throttle(request):
    key = request.client.host if request.client else 'unknown'
    attempts = request.app.state.auth_attempts
    # Bounded key count. Local deployments normally use just loopback.
    if len(attempts) > 10000:
        attempts.clear()
    history = attempts[key]
    while history and history[0] < time.monotonic() - 60:
        history.popleft()
    if len(history) >= 10:
        raise HTTPException(429, 'Too many attempts. Retry in one minute.')
    history.append(time.monotonic())


def issue(db, user, response, secure):
    token = secrets.token_urlsafe(48)
    db.add(AuthToken(digest=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires=time.time()+28800))
    db.commit()
    response.set_cookie('cortia_session', token, httponly=True, secure=secure, samesite='strict', max_age=28800, path='/')

@router.post('/register', status_code=201)
def register(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    throttle(request)
    user = User(username=data.username.lower(), password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Username unavailable')
    issue(db, user, response, request.app.state.settings.secure_cookie)
    return public(user)

@router.post('/login')
def login(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    throttle(request)
    user = db.query(User).filter_by(username=data.username.lower()).first()
    try:
        valid = passwords.verify(user.password_hash if user else DUMMY_HASH, data.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, 'Invalid username or password')
    issue(db, user, response, request.app.state.settings.secure_cookie)
    return public(user)

@router.post('/logout')
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get('cortia_session', '')
    record = db.get(AuthToken, hashlib.sha256(token.encode()).hexdigest())
    if record:
        db.delete(record)
        db.commit()
    response.delete_cookie('cortia_session', path='/')
    return {'ok':True}

@router.get('/me')
def me(user=Depends(current_user)):
    return public(user)
