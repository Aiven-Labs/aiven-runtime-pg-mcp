"""Require a bearer token, then run postgres-mcp over streamable HTTP."""
import hmac
import os
import sys


def read_settings(env):
    token = env.get("MCP_AUTH_TOKEN", "")
    if len(token) < 32:
        raise ValueError("MCP_AUTH_TOKEN must contain at least 32 characters.")
    access_mode = env.get("ACCESS_MODE", "restricted")
    if access_mode not in ("restricted", "unrestricted"):
        raise ValueError("ACCESS_MODE must be restricted or unrestricted.")
    if not env.get("DATABASE_URI"):
        raise ValueError("Set DATABASE_URI to the PostgreSQL service URI.")
    return token, access_mode


async def respond(send, status, body, headers=()):
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain"), *headers]})
    await send({"type": "http.response.body", "body": body})


class BearerAuth:
    """ASGI middleware that serves /health and rejects requests without the token."""

    def __init__(self, app, token):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
        elif scope["type"] != "http":
            # postgres-mcp serves no WebSockets, so refuse them instead of passing them unchecked.
            await send({"type": "websocket.close", "code": 1008})
        elif scope["path"] == "/health":
            await respond(send, 200, b"ok")
        elif not hmac.compare_digest(dict(scope["headers"]).get(b"authorization", b""), self.expected):
            await respond(send, 401, b"Unauthorized", [(b"www-authenticate", b"Bearer")])
        else:
            await self.app(scope, receive, send)


def main():
    token, access_mode = read_settings(os.environ)
    # Imported here so the tests run without postgres-mcp installed.
    import postgres_mcp

    mcp = postgres_mcp.server.mcp
    # postgres-mcp builds its server for localhost, which makes the MCP SDK reject
    # every other Host header. Runtime serves the app on its own hostname.
    mcp.settings.transport_security = None
    build_app = mcp.streamable_http_app
    mcp.streamable_http_app = lambda: BearerAuth(build_app(), token)
    sys.argv = ["postgres-mcp", "--access-mode", access_mode, "--transport", "streamable-http",
                "--streamable-http-host", "0.0.0.0", "--streamable-http-port", "8000"]
    postgres_mcp.main()


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        sys.exit(1)
