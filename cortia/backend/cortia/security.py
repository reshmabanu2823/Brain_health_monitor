"""Bound request bodies before multipart parsing, including chunked transfers."""
from starlette.responses import JSONResponse

class BodyLimit:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            part = message.get('body',b'')
            if len(body)+len(part) > self.limit:
                response = JSONResponse({'detail':'Request exceeds upload limit'},status_code=413)
                return await response(scope,receive,send)
            body.extend(part)
            if not message.get('more_body',False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)
