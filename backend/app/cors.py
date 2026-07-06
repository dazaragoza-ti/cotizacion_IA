"""
Middleware CORS para desarrollo local (Flutter web usa puertos aleatorios).
"""
import re as _re


class _LocalhostCORSMiddleware:
    """Permite cualquier origen http://localhost:* en desarrollo."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode()
            is_localhost = bool(_re.match(r"http://localhost(:\d+)?$", origin))
            if is_localhost:
                async def send_with_cors(message):
                    if message["type"] == "http.response.start":
                        headers_list = list(message.get("headers", []))
                        headers_list += [
                            (b"access-control-allow-origin", origin.encode()),
                            (b"access-control-allow-credentials", b"true"),
                            (b"access-control-allow-methods", b"*"),
                            (b"access-control-allow-headers", b"*"),
                        ]
                        message = {**message, "headers": headers_list}
                    await send(message)

                # Responder preflight OPTIONS directamente
                if scope.get("method") == "OPTIONS":
                    response_headers = [
                        (b"access-control-allow-origin", origin.encode()),
                        (b"access-control-allow-credentials", b"true"),
                        (b"access-control-allow-methods", b"*"),
                        (b"access-control-allow-headers", b"*"),
                        (b"content-length", b"0"),
                    ]
                    await send({"type": "http.response.start", "status": 204, "headers": response_headers})
                    await send({"type": "http.response.body", "body": b""})
                    return

                await self.app(scope, receive, send_with_cors)
                return
        await self.app(scope, receive, send)
