import hmac

from starlette.responses import JSONResponse


class TokenAuthMiddleware:
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if self.token and scope["type"] == "http" and scope["path"].startswith("/api/"):
            supplied = dict(scope["headers"]).get(b"x-api-key", b"").decode("latin1")
            if not hmac.compare_digest(supplied, self.token):
                return await JSONResponse({"detail": "Unauthorized"}, 401)(scope, receive, send)
        await self.app(scope, receive, send)
