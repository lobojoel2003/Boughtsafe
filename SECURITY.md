# Security policy

## Supported versions

Security fixes go into the latest release. Self-hosters should track `latest` or the
newest `X.Y` image tag.

## Reporting a vulnerability

Please **don't** open a public issue. Report it privately through
[GitHub Security Advisories](https://github.com/lobojoel2003/Boughtsafe/security/advisories/new).
Include steps to reproduce and the version and build (Settings → About, or `GET /v1/meta`).
You should get a reply within a week.

## Design notes for reviewers

- Purchases are stored only in the browser's IndexedDB. `POST /v1/match` processes items
  in memory and responds with `Cache-Control: no-store`. Request bodies are never logged.
- Push subscriptions store an endpoint, its keys and 16-bit watch buckets, never barcodes.
  Endpoints must belong to a known browser push service, so the server can't be used to
  send requests to arbitrary hosts.
- The web app ships a hash-based Content-Security-Policy. nginx adds `X-Frame-Options`,
  `nosniff`, `Referrer-Policy` and a restrictive `Permissions-Policy`.
- Both container images run as non-root users.
