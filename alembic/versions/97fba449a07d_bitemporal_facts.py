"""bitemporal_facts

Revision ID: 97fba449a07d
Revises: a3a0f10c0273
Create Date: 2026-09-20 22:05:36.596733

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97fba449a07d"
down_revision: str | Sequence[str] | None = "a3a0f10c0273"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add bi-temporal columns, graph triple columns, and indexes to facts."""
    with op.batch_alter_table("facts") as batch_op:
        batch_op.add_column(
            sa.Column("valid_from", sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        batch_op.add_column(sa.Column("valid_to", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("expired_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("subject", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(
            sa.Column("predicate", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(sa.Column("object", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("superseded_by_id", sa.Uuid(), nullable=True))

        batch_op.create_index(
            "idx_tenant_fact_bitemporal",
            ["tenant_id", "valid_from", "valid_to", "created_at", "expired_at"],
            unique=False,
        )
        batch_op.create_index(
            "idx_tenant_fact_subject_predicate",
            ["tenant_id", "subject", "predicate"],
            unique=False,
        )
        batch_op.create_index(
            "idx_tenant_fact_superseded_by", ["tenant_id", "superseded_by_id"], unique=False
        )
        batch_op.create_index(
            "idx_tenant_fact_system", ["tenant_id", "created_at", "expired_at"], unique=False
        )
        batch_op.create_index(
            "idx_tenant_fact_valid", ["tenant_id", "valid_from", "valid_to"], unique=False
        )
        batch_op.create_index("ix_facts_object", ["object"], unique=False)
        batch_op.create_index("ix_facts_predicate", ["predicate"], unique=False)
        batch_op.create_index("ix_facts_subject", ["subject"], unique=False)
        batch_op.create_foreign_key(
            "fk_facts_superseded_by_id_facts", "facts", ["superseded_by_id"], ["id"]
        )


def downgrade() -> None:
    """Downgrade schema to remove bi-temporal columns and indexes from facts."""
    with op.batch_alter_table("facts") as batch_op:
        batch_op.drop_constraint("fk_facts_superseded_by_id_facts", type_="foreignkey")
        batch_op.drop_index("ix_facts_subject")
        batch_op.drop_index("ix_facts_predicate")
        batch_op.drop_index("ix_facts_object")
        batch_op.drop_index("idx_tenant_fact_valid")
        batch_op.drop_index("idx_tenant_fact_system")
        batch_op.drop_index("idx_tenant_fact_superseded_by")
        batch_op.drop_index("idx_tenant_fact_subject_predicate")
        batch_op.drop_index("idx_tenant_fact_bitemporal")
        batch_op.drop_column("superseded_by_id")
        batch_op.drop_column("object")
        batch_op.drop_column("predicate")
        batch_op.drop_column("subject")
        batch_op.drop_column("expired_at")
        batch_op.drop_column("valid_to")
        batch_op.drop_column("valid_from")
