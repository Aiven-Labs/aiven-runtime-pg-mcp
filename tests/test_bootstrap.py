import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bootstrap as b

TOKEN = "t" * 32
VALID_ENV = {"MCP_AUTH_TOKEN": TOKEN, "DATABASE_URI": "postgresql://user:secret@db:5432/defaultdb"}


def request(path, authorization=None, scope_type="http"):
    """Send one request through BearerAuth; return its status or close code and whether the wrapped app ran."""
    sent = []
    reached = []

    async def app(scope, receive, send):
        reached.append(scope)

    async def send(message):
        sent.append(message)

    headers = [(b"authorization", authorization.encode())] if authorization else []
    scope = {"type": scope_type, "path": path, "headers": headers}
    asyncio.run(b.BearerAuth(app, TOKEN)(scope, None, send))
    return (sent[0].get("status", sent[0].get("code")) if sent else None), bool(reached)


class WhenMcpAuthTokenIsNotSet(unittest.TestCase):
    def test_it_refuses_to_start(self):
        # Without a token the public Runtime URL would give anyone SQL access.
        with self.assertRaises(ValueError):
            b.read_settings({"DATABASE_URI": VALID_ENV["DATABASE_URI"]})


class WhenMcpAuthTokenIsShorterThan32Characters(unittest.TestCase):
    def test_it_refuses_to_start(self):
        with self.assertRaises(ValueError):
            b.read_settings({**VALID_ENV, "MCP_AUTH_TOKEN": "t" * 31})


class WhenDatabaseUriIsNotSet(unittest.TestCase):
    def test_it_refuses_to_start(self):
        with self.assertRaises(ValueError):
            b.read_settings({"MCP_AUTH_TOKEN": TOKEN})


class WhenAccessModeIsNotSet(unittest.TestCase):
    def test_it_uses_restricted_mode(self):
        # The database account is a service administrator, so writes are opt-in.
        self.assertEqual(b.read_settings(VALID_ENV), (TOKEN, "restricted"))


class WhenAccessModeIsUnrestricted(unittest.TestCase):
    def test_it_uses_unrestricted_mode(self):
        self.assertEqual(b.read_settings({**VALID_ENV, "ACCESS_MODE": "unrestricted"}), (TOKEN, "unrestricted"))


class WhenAccessModeIsUnknown(unittest.TestCase):
    def test_it_refuses_to_start(self):
        with self.assertRaises(ValueError):
            b.read_settings({**VALID_ENV, "ACCESS_MODE": "read-only"})


class WhenTheRequestHasNoAuthorizationHeader(unittest.TestCase):
    def test_it_responds_401_without_reaching_the_mcp_server(self):
        self.assertEqual(request("/mcp"), (401, False))


class WhenTheRequestHasAWrongToken(unittest.TestCase):
    def test_it_responds_401_without_reaching_the_mcp_server(self):
        self.assertEqual(request("/mcp", "Bearer " + "x" * 32), (401, False))


class WhenTheRequestSendsTheTokenWithoutTheBearerScheme(unittest.TestCase):
    def test_it_responds_401_without_reaching_the_mcp_server(self):
        self.assertEqual(request("/mcp", TOKEN), (401, False))


class WhenTheRequestHasTheToken(unittest.TestCase):
    def test_it_passes_the_request_to_the_mcp_server(self):
        self.assertEqual(request("/mcp", f"Bearer {TOKEN}"), (None, True))


class WhenTheConnectionIsAWebSocket(unittest.TestCase):
    def test_it_closes_the_connection_without_reaching_the_mcp_server(self):
        # Only HTTP requests get the token check, so nothing else may pass.
        self.assertEqual(request("/mcp", f"Bearer {TOKEN}", "websocket"), (1008, False))


class WhenTheServerSendsALifespanEvent(unittest.TestCase):
    def test_it_passes_the_event_to_the_mcp_server(self):
        # The MCP session manager starts during the lifespan startup event.
        self.assertEqual(request("", scope_type="lifespan"), (None, True))


class WhenTheRequestIsForHealth(unittest.TestCase):
    def test_it_responds_200_without_a_token(self):
        # The container health check has no token.
        self.assertEqual(request("/health"), (200, False))


if __name__ == "__main__":
    unittest.main()
