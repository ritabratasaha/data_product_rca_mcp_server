FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY manifests/ manifests/

RUN pip install --no-cache-dir .

ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MANIFESTS_PATH=/app/manifests
ENV PROMETHEUS_PORT=9090

EXPOSE 8000
EXPOSE 9090

CMD ["rca-server"]
