"""``boughtsafe`` command line: serve, sync, migrate, seed, vapid-keys."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__

if TYPE_CHECKING:
    from alembic.config import Config


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _alembic_config() -> Config:
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    return cfg


def cmd_migrate(_: argparse.Namespace) -> int:
    from alembic import command

    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)
    command.upgrade(_alembic_config(), "head")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.migrate:
        cmd_migrate(args)
    uvicorn.run(
        "boughtsafe.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level="info",
    )
    return 0


def _run_sync(names: list[str] | None, full: bool | None) -> bool:
    from .config import get_settings
    from .db import session_scope
    from .ingest import prune_runs, sync_all
    from .matching import catalog_version
    from .push import notify

    settings = get_settings()
    with session_scope() as session:
        results = sync_all(session, settings, names=names, full=full)
        buckets = set().union(*(r.changed_buckets for r in results)) if results else set()
        if buckets:
            notify(session, settings, buckets, catalog_version(session))
        prune_runs(session)
    for r in results:
        state = "ok" if r.ok else f"FAILED ({r.error})"
        counts = f"fetched={r.fetched} created={r.created} updated={r.updated}"
        print(f"{r.source:5} {r.mode:11} {counts} {state}")
    return all(r.ok for r in results)


def cmd_sync(args: argparse.Namespace) -> int:
    from .config import get_settings

    names = args.source or None
    full = True if args.full else None
    if not args.loop:
        return 0 if _run_sync(names, full) else 1

    stop = False

    def _stop(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    interval = (args.interval or get_settings().sync_interval_minutes) * 60
    while not stop:
        started = time.monotonic()
        try:
            _run_sync(names, full)
        except Exception:  # never let one bad cycle kill the worker
            logging.getLogger("boughtsafe.sync").exception("sync cycle crashed")
        full = None  # only the first loop iteration honours --full
        while not stop and time.monotonic() - started < interval:
            time.sleep(1)
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Load raw upstream records from a JSON file: ``{"fda": [...], "cpsc": [...]}``."""
    from .config import get_settings
    from .db import session_scope
    from .ingest import SyncResult, upsert
    from .sources import build_sources

    settings = get_settings()
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    with session_scope() as session:
        for source in build_sources(settings):
            raws = data.get(source.name) or []
            result = SyncResult(source=source.name, mode="seed")
            batch = [n for n in (source.normalize(r) for r in raws) if n is not None]
            upsert(session, batch, result)
            print(f"{source.name:5} seeded created={result.created} updated={result.updated}")
    return 0


def cmd_vapid(_: argparse.Namespace) -> int:
    from .push import generate_vapid_keys

    public, private = generate_vapid_keys()
    print(f"BOUGHTSAFE_VAPID_PUBLIC_KEY={public}")
    print(f"BOUGHTSAFE_VAPID_PRIVATE_KEY={private}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boughtsafe", description=__doc__)
    parser.add_argument("--version", action="version", version=f"boughtsafe {__version__}")
    parser.add_argument("--log-level", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the HTTP API")
    p.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container default
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-migrate", dest="migrate", action="store_false")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("sync", help="mirror recall feeds into the database")
    p.add_argument("--source", action="append", choices=["fda", "fsis", "cpsc"])
    p.add_argument("--full", action="store_true", help="re-download everything")
    p.add_argument("--loop", action="store_true", help="keep syncing on an interval")
    p.add_argument("--interval", type=int, help="minutes between syncs (default from settings)")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("migrate", help="apply database migrations")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("seed", help="load raw recall records from a JSON file")
    p.add_argument("file")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("vapid-keys", help="generate Web Push keys")
    p.set_defaults(func=cmd_vapid)

    args = parser.parse_args(argv)
    from .config import get_settings

    _setup_logging(args.log_level or get_settings().log_level)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
