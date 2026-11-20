FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# The latest postgres-mcp release (0.3.0) has no streamable HTTP transport,
# so build a pinned commit from source with its locked dependencies.
ARG POSTGRES_MCP_COMMIT=15c8e33353546148acc2d8bd784551cf3905d1e2
ARG POSTGRES_MCP_SHA256=e53517df89664cfe5888dddf251947445dce2f294fe1a64b6579cb2377c8b20b
ADD https://github.com/crystaldba/postgres-mcp/archive/${POSTGRES_MCP_COMMIT}.tar.gz /tmp/postgres-mcp.tar.gz
RUN echo "${POSTGRES_MCP_SHA256}  /tmp/postgres-mcp.tar.gz" | sha256sum -c - \
    && mkdir /app \
    && tar -xzf /tmp/postgres-mcp.tar.gz --strip-components=1 -C /app \
    && rm /tmp/postgres-mcp.tar.gz \
    && pip install --no-cache-dir uv==0.13.9 \
    && UV_PYTHON_DOWNLOADS=0 uv sync --project /app --frozen --no-dev --no-cache \
    && useradd --system app

COPY bootstrap.py /starter/bootstrap.py
# Runtime shows every ENV line as a field on the deploy screen, so these two
# are empty placeholders for the deployer to fill. Add no other ENV lines:
# a PATH copied without the base image's value would break the container.
ENV DATABASE_URI="" MCP_AUTH_TOKEN=""
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD /app/.venv/bin/python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).read() == b'ok'"
ENTRYPOINT ["/app/.venv/bin/python", "-u", "/starter/bootstrap.py"]
CMD []
