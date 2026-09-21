"""Usage event attribution fields and indexes (T-211).

Revision ID: c8f1e29a3b47
Revises: 7a8e10b42c91
Create Date: 2026-09-21

Adds nullable document_id, extraction_run_id, and user_id to usage_events,
with composite indexes leading with tenant_id and NO foreign keys.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f1e29a3b47"
down_revision: str | None = "7a8e10b42c91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add attribution columns and tenant-leading composite indexes."""
    op.add_column("usage_events", sa.Column("document_id", sa.Uuid(), nullable=True))
    op.add_column("usage_events", sa.Column("extraction_run_id", sa.Uuid(), nullable=True))
    op.add_column("usage_events", sa.Column("user_id", sa.Uuid(), nullable=True))

    op.create_index(
        "idx_tenant_usage_document",
        "usage_events",
        ["tenant_id", "document_id"],
    )
    op.create_index(
        "idx_tenant_usage_run",
        "usage_events",
        ["tenant_id", "extraction_run_id"],
    )
    op.create_index(
        "idx_tenant_usage_user",
        "usage_events",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    """Remove attribution columns and indexes."""
    op.drop_index("idx_tenant_usage_user", table_name="usage_events")
    op.drop_index("idx_tenant_usage_run", table_name="usage_events")
    op.drop_index("idx_tenant_usage_document", table_name="usage_events")

    op.drop_column("usage_events", "user_id")
    op.drop_column("usage_events", "extraction_run_id")
    op.drop_column("usage_events", "document_id")
