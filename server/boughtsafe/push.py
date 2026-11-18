"""Web Push alerts that never reveal what anyone bought.

Devices register *watch buckets*: the first 16 bits of a salted SHA-256 of each
barcode they own (see :func:`boughtsafe.gtin.bucket`). When a sync adds or
changes a recall, the server pushes a wake-up carrying only the buckets that
were hit. The service worker then checks its own purchases, confirms the match
with ``/v1/match`` for the handful of items in those buckets, and shows a
notification only if something you own is really affected.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import PushSubscription, utcnow

log = logging.getLogger(__name__)


def generate_vapid_keys() -> tuple[str, str]:
    """Return ``(public, private)`` VAPID keys, both base64url without padding."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    priv = key.private_numbers().private_value.to_bytes(32, "big")
    pub = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    return b64(pub), b64(priv)


def send(settings: Settings, sub: PushSubscription, payload: dict[str, Any]) -> bool:
    """Send one push. Returns ``False`` when the subscription is gone for good."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload, separators=(",", ":")),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=24 * 3600,
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return False
        log.warning("push to %s… failed: %s", sub.endpoint[:40], exc)
        return True


def notify(
    session: Session, settings: Settings, buckets: Iterable[str], catalog_version: str
) -> int:
    """Wake every device watching one of ``buckets``. Returns pushes sent."""
    hit = set(buckets)
    if not hit or not settings.push_enabled:
        return 0
    sent = 0
    for sub in session.scalars(select(PushSubscription)).all():
        overlap = sorted(hit.intersection(sub.buckets or []))
        if not overlap:
            continue
        if send(settings, sub, {"t": "recall", "b": overlap, "v": catalog_version}):
            sub.last_push_at = utcnow()
            sent += 1
        else:
            session.delete(sub)
    session.commit()
    log.info("push: %d device(s) woken for %d bucket(s)", sent, len(hit))
    return sent
