# syntax=docker/dockerfile:1.7
# Boughtsafe web app (static files) behind nginx, proxying /api to the API.
# Build from the repository root:
#   docker build -f web/Dockerfile -t boughtsafe-web .

FROM --platform=$BUILDPLATFORM node:26-alpine AS build
WORKDIR /src
COPY VERSION ./
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci --ignore-scripts --no-audit --no-fund
COPY web ./web
ARG BUILD_NUMBER=dev
ARG GIT_SHA=local
ENV BUILD_NUMBER=${BUILD_NUMBER} GIT_SHA=${GIT_SHA}
RUN cd web && npx svelte-kit sync && npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
ARG VERSION=0.0.0
ARG BUILD_NUMBER=dev
ARG GIT_SHA=local
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="Boughtsafe web" \
      org.opencontainers.image.description="Installable web app: recall alerts matched to what you bought." \
      org.opencontainers.image.source="https://github.com/lobojoel2003/Boughtsafe" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      io.boughtsafe.build-number="${BUILD_NUMBER}"
ENV API_UPSTREAM=http://api:8000
COPY web/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY web/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /src/web/build /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
