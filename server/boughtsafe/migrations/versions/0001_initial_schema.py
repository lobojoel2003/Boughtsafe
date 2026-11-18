"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-18 19:34:18.858303
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_cache",
        sa.Column("gtin", sa.String(length=14), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("gtin"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column(
            "buckets",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_push_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("endpoint"),
    )
    op.create_table(
        "recalls",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product", sa.Text(), nullable=False),
        sa.Column("firm", sa.Text(), nullable=True),
        sa.Column("brand_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "hazard",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("classification", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("codes", sa.Text(), nullable=False),
        sa.Column("covers_all_codes", sa.Boolean(), nullable=False),
        sa.Column("has_codes", sa.Boolean(), nullable=False),
        sa.Column("distribution", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "refund",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("recall_date", sa.Date(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "raw",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recalls_event_id"), "recalls", ["event_id"], unique=False)
    op.create_index(op.f("ix_recalls_recall_date"), "recalls", ["recall_date"], unique=False)
    op.create_index(op.f("ix_recalls_source"), "recalls", ["source"], unique=False)
    op.create_index(op.f("ix_recalls_updated_at"), "recalls", ["updated_at"], unique=False)
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("fetched", sa.Integer(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_runs_source"), "sync_runs", ["source"], unique=False)
    op.create_table(
        "recall_gtins",
        sa.Column("recall_id", sa.String(length=80), nullable=False),
        sa.Column("gtin", sa.String(length=14), nullable=False),
        sa.Column("bucket", sa.String(length=4), nullable=False),
        sa.ForeignKeyConstraint(["recall_id"], ["recalls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recall_id", "gtin"),
    )
    op.create_index(op.f("ix_recall_gtins_bucket"), "recall_gtins", ["bucket"], unique=False)
    op.create_index("ix_recall_gtins_gtin", "recall_gtins", ["gtin"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recall_gtins_gtin", table_name="recall_gtins")
    op.drop_index(op.f("ix_recall_gtins_bucket"), table_name="recall_gtins")
    op.drop_table("recall_gtins")
    op.drop_index(op.f("ix_sync_runs_source"), table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index(op.f("ix_recalls_updated_at"), table_name="recalls")
    op.drop_index(op.f("ix_recalls_source"), table_name="recalls")
    op.drop_index(op.f("ix_recalls_recall_date"), table_name="recalls")
    op.drop_index(op.f("ix_recalls_event_id"), table_name="recalls")
    op.drop_table("recalls")
    op.drop_table("push_subscriptions")
    op.drop_table("product_cache")
