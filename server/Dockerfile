# syntax=docker/dockerfile:1.7
# Boughtsafe API and sync worker. Build from the repository root:
#   docker build -f server/Dockerfile -t boughtsafe-api .

FROM --platform=$BUILDPLATFORM python:3.15-slim AS build
WORKDIR /src
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY server/pyproject.toml server/README.md server/alembic.ini ./
COPY server/boughtsafe ./boughtsafe
# Only Boughtsafe's own (pure-Python) wheel is built here; each target platform
# installs its dependencies itself in the final stage.
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.15-slim
ARG VERSION=0.0.0
ARG BUILD_NUMBER=dev
ARG GIT_SHA=local
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="Boughtsafe API" \
      org.opencontainers.image.description="Mirrors FDA, USDA FSIS and CPSC recalls and matches them to purchases." \
      org.opencontainers.image.source="https://github.com/lobojoel2003/Boughtsafe" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      io.boughtsafe.build-number="${BUILD_NUMBER}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOUGHTSAFE_BUILD_NUMBER=${BUILD_NUMBER} \
    BOUGHTSAFE_GIT_SHA=${GIT_SHA}
RUN useradd --system --uid 10001 --create-home --home-dir /app boughtsafe
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
USER 10001
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status != 200)"]
ENTRYPOINT ["boughtsafe"]
CMD ["serve"]
