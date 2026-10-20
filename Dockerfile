FROM ghcr.io/astral-sh/uv:0.13.1-python3.13-trixie-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM python:3.13-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/antomanc/scalebridge" \
      org.opencontainers.image.description="Bluetooth bathroom scales to Garmin Connect" \
      org.opencontainers.image.licenses="MIT"
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SCALEBRIDGE_CONFIG=/config/config.yaml
# BlueZ is reached over the host's D-Bus socket, which any user may talk to,
# so the service runs unprivileged.
RUN useradd --system --uid 1000 --home-dir /data scalebridge && mkdir -p /data \
    && chown scalebridge /data
USER scalebridge
WORKDIR /data
VOLUME ["/data"]
ENTRYPOINT ["scalebridge"]
CMD ["run"]
