# Postgres MCP starter for Aiven Runtime

Run [Postgres MCP Pro](https://github.com/crystaldba/postgres-mcp) on **Aiven Runtime** with **Aiven for PostgreSQL**. AI assistants such as Claude Code and Cursor can then inspect schemas, run SQL, explain query plans and check database health.

**This is a demo template.** Use it to try Postgres MCP with Aiven Runtime, on a database that holds no production or sensitive data. It protects the endpoint with one shared token and connects with the service administrator account. See [Security](#security) for the limits.

## What starts up

```text
MCP client --HTTPS + bearer token--> Aiven Runtime :8000
                                           |
                                    token check (bootstrap.py)
                                           |
                                      postgres-mcp
                                           |
                                    Aiven PostgreSQL
```

`bootstrap.py` wraps the upstream server. It adds two things:

- **A required bearer token.** postgres-mcp has no authentication, and a Runtime application has a public URL. The wrapper rejects every request without `Authorization: Bearer <MCP_AUTH_TOKEN>`. The container does not start without the token.
- **Read-only by default.** The server starts with `--access-mode=restricted`. Set `ACCESS_MODE=unrestricted` to allow writes.

The MCP endpoint is `/mcp` and uses the streamable HTTP transport. `/health` answers `ok` without a token.

## Deploy on Aiven Runtime

Generate a token first: `openssl rand -hex 32`. Then choose the manifest file that fits your database.

| Your database | Manifest file | Who fills `DATABASE_URI` |
| --- | --- | --- |
| A new Aiven for PostgreSQL service | `compose.aiven.yaml` | Runtime |
| An existing Aiven for PostgreSQL service | `compose.aiven.yaml` | Runtime |
| Any other PostgreSQL, or a role with fewer rights | `Dockerfile` | You |

### With a new or existing Aiven for PostgreSQL service

1. Create a Runtime application from this repository and select **compose.aiven.yaml**.
2. Review the PostgreSQL service. Runtime creates a new one by default. To use an existing service, edit the PostgreSQL card and choose it.
3. For a new service, select PostgreSQL 17. Runtime ignores the version in the manifest and picks the latest stable version. postgres-mcp focuses its testing on versions 15, 16 and 17.
4. Review the credential integration. It must fill `DATABASE_URI` with the service URI.
5. Fill `MCP_AUTH_TOKEN` with your token and mark it as a secret.
6. Use HTTP port **8000** and one replica. MCP sessions live in memory.
7. Deploy, then connect your MCP client to `https://<application-url>/mcp`.

### With any other PostgreSQL database

Use this to connect to a database outside Aiven, or with a PostgreSQL role that has fewer rights than the service administrator. Runtime creates no database and no integration in this case.

1. Create a Runtime application from this repository and select **Dockerfile**.
2. Fill `DATABASE_URI` with the connection URI, for example `postgresql://reader:<password>@db.example.com:5432/mydb?sslmode=require`. Mark it as a secret, because it contains the password.
3. Fill `MCP_AUTH_TOKEN` with your token and mark it as a secret.
4. Use HTTP port **8000** and one replica.
5. Deploy, then connect your MCP client to `https://<application-url>/mcp`.

The database must accept connections from the Runtime application.

### Settings

| Variable | Required | Value |
| --- | --- | --- |
| `DATABASE_URI` | yes | PostgreSQL connection URI. The integration provides it when you deploy with `compose.aiven.yaml`. |
| `MCP_AUTH_TOKEN` | yes | Shared secret, at least 32 characters. Keep it in a Runtime secret. |
| `ACCESS_MODE` | no | `restricted` (default) or `unrestricted`. |

## Connect a client

Claude Code:

```sh
claude mcp add --transport http postgres https://<application-url>/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

Cursor and other clients that read `mcp.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "url": "https://<application-url>/mcp",
      "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
    }
  }
}
```

## Security

- **Everyone shares one token.** The server cannot tell users apart. Give the token only to people who may read the whole database.
- **Rotate by changing the secret.** Set a new `MCP_AUTH_TOKEN` in Runtime, redeploy, and update every client.
- **Runtime OIDC authentication does not work here.** It uses a browser login, and MCP clients cannot complete it.
- **The integration provides the service administrator account.** In `unrestricted` mode a client can run any SQL, including `DROP`. For shared use, create a PostgreSQL role with fewer rights and put its URI in `DATABASE_URI`.
- **Restricted mode is enforced by postgres-mcp, not by PostgreSQL.** It parses each statement and runs it in a read-only transaction. A read-only PostgreSQL role is the stronger guarantee.

## Query statistics and index tuning

- **The slow query report (`get_top_queries`) needs the `pg_stat_statements` extension.** This step is optional. On Aiven for PostgreSQL, run this once with `psql`, because restricted mode blocks it:

  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
  ```

- **The index advisor does not work on Aiven for PostgreSQL.** `analyze_workload_indexes`, `analyze_query_indexes` and hypothetical indexes in `explain_query` need the `hypopg` extension, which Aiven does not offer.

The local demo database has neither extension, so these tools are unavailable there. All other tools work without extensions.

## Local demo

Requires Docker Compose v2 or `podman compose`.

1. Copy `.env.example` to `.env`.
2. Run `openssl rand -hex 32` twice. Use one value for `POSTGRES_PASSWORD` and the other for `MCP_AUTH_TOKEN`.
3. Run `docker compose up --build -d`.
4. Connect your MCP client to `http://localhost:8000/mcp` with the token.

`docker compose down` keeps the PostgreSQL data. `docker compose down -v` deletes it.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Upgrade postgres-mcp

The latest postgres-mcp release (0.3.0) does not include the streamable HTTP transport. The Dockerfile therefore builds a pinned upstream commit with its locked dependencies. To upgrade, change `POSTGRES_MCP_COMMIT` in the Dockerfile and set `POSTGRES_MCP_SHA256` to the checksum of the new archive:

```sh
curl -sL https://github.com/crystaldba/postgres-mcp/archive/<commit>.tar.gz | shasum -a 256
```

## References

- [Postgres MCP Pro](https://github.com/crystaldba/postgres-mcp)
- [Aiven Runtime Compose manifests](https://aiven.io/docs/products/runtime/manifest-files/compose-files)
- [Aiven Runtime secrets and variables](https://aiven.io/docs/products/runtime/secrets-and-variables)

## License

The template code is licensed under the [MIT License](LICENSE). Postgres MCP Pro, PostgreSQL and other third-party components retain their own licenses.
