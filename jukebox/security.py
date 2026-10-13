"""Bounded ASGI input, host protection, same-origin mutations, browser hardening."""
from urllib.parse import urlsplit
from starlette.responses import JSONResponse

MAX_BODY = 8*1024*1024

class LocalOnly:
    def __init__(self, app):
        self.app=app

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        headers={k.decode().lower():v.decode() for k,v in scope['headers']}
        host=headers.get('host','')
        try:
            hostname=urlsplit('//'+host).hostname
        except ValueError:
            hostname=None
        reason=None
        if hostname not in ('localhost','127.0.0.1','::1','testserver'):
            reason='Only local host requests are accepted.'
        if scope['method'] not in ('GET','HEAD'):
            expected=scope.get('scheme','http')+'://'+host
            if headers.get('x-jukebox')!='1' or headers.get('origin',expected)!=expected or headers.get('sec-fetch-site')=='cross-site':
                reason='Request blocked. Open Jukebox directly on localhost and try again.'
        if reason:
            return await JSONResponse({'detail':reason},403)(scope,receive,send)
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            body.extend(message.get('body',b''))
            if len(body)>MAX_BODY:
                return await JSONResponse({'detail':'Upload is too large. Use an MP3 or WAV reference under 6 MB.'},413)(scope,receive,send)
            if not message.get('more_body',False):
                break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        async def secure_send(message):
            if message['type']=='http.response.start':
                message['headers'] += [
                    (b'x-content-type-options',b'nosniff'),
                    (b'referrer-policy',b'no-referrer'),
                    (b'cache-control',b'no-store'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]
            await send(message)
        await self.app(scope,bounded_receive,secure_send)
