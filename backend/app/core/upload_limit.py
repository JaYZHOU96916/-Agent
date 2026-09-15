from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    """Count actual ASGI bytes, including requests without Content-Length."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length."}, 400)(scope, receive, send)
        if length > self.max_bytes:
            return await JSONResponse({"detail": "Request exceeds upload size limit."}, 413)(scope, receive, send)
        size = 0
        exceeded = False

        async def limited_receive():
            nonlocal size, exceeded
            message = await receive()
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                exceeded = True
                # Starlette cleans up temporary multipart files for this exception.
                raise MultiPartException("Request exceeds upload size limit.")
            return message

        async def limited_send(message):
            if exceeded and message["type"] == "http.response.start":
                message = {**message, "status": 413}
            await send(message)

        await self.app(scope, limited_receive, limited_send)
