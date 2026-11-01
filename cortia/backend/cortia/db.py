from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

def uid():
    return str(uuid4())

def now():
    return datetime.now(timezone.utc).isoformat()

def setup(settings):
    settings.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for folder in ('raw', 'mri', 'reports'):
        (settings.data_dir/folder).mkdir(mode=0o700, exist_ok=True)
    url = settings.database_url or f'sqlite:///{settings.data_dir}/cortia.db'
    engine = create_engine(url, connect_args={'check_same_thread':False, 'timeout':30} if url.startswith('sqlite') else {})
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def pragmas(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    from . import models
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        version = db.get(models.SchemaVersion, 1)
        if version is None:
            db.add(models.SchemaVersion(id=1, version=1))
            db.commit()
        elif version.version != 1:
            raise RuntimeError('Unsupported database schema. Back up data before migrating.')
        # Crashed process cannot leave a recording masquerading as active.
        for row in db.query(models.Recording).filter_by(state='recording').all():
            row.state = 'interrupted'
            row.ended_at = now()
            row.end_reason = 'Backend restarted; final in-memory samples may be unavailable.'
        db.commit()
    if url.startswith('sqlite'):
        (settings.data_dir/'cortia.db').chmod(0o600)
    return engine, factory
