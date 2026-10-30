"""debts: debt table, repayment links on transactions and planned fixed costs

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 10:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("creditor", sa.String(length=128), nullable=True),
        sa.Column("original_cents", sa.Integer(), nullable=False),
        sa.Column("opening_balance_cents", sa.Integer(), nullable=False),
        sa.Column("monthly_rate_cents", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("original_cents > 0", name=op.f("ck_debts_original_positive")),
        sa.CheckConstraint(
            "opening_balance_cents >= 0 AND opening_balance_cents <= original_cents",
            name=op.f("ck_debts_opening_balance_in_range"),
        ),
        sa.CheckConstraint(
            "monthly_rate_cents IS NULL OR monthly_rate_cents > 0", name=op.f("ck_debts_rate_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_debts")),
    )
    # Batch mode rebuilds the tables, so the foreign keys are reflected with their names
    # and ON DELETE rules. Migrations run without PRAGMA foreign_keys, so the rebuild
    # cannot cascade into rows that reference these tables.
    with op.batch_alter_table("transactions", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("debt_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_transactions_debt_id_debts"), "debts", ["debt_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_check_constraint(
            batch_op.f("ck_transactions_debt_only_on_expense"), "debt_id IS NULL OR type = 'expense'"
        )
        batch_op.create_index(batch_op.f("ix_transactions_debt_id"), ["debt_id"], unique=False)
    with op.batch_alter_table("recurring_expenses", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("debt_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_recurring_expenses_debt_id_debts"),
            "debts",
            ["debt_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(batch_op.f("ix_recurring_expenses_debt_id"), ["debt_id"], unique=False)

    # Existing installations get the new default category; an empty table is seeded at startup.
    conn = op.get_bind()
    has_categories = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar_one() > 0
    exists = conn.execute(
        sa.text("SELECT 1 FROM categories WHERE kind = 'fixed' AND name = 'Kredite und Raten'")
    ).first()
    if has_categories and not exists:
        conn.execute(
            sa.text(
                "INSERT INTO categories (name, kind, color, is_default, archived, created_at)"
                " VALUES ('Kredite und Raten', 'fixed', '#b45309', 1, 0, :now)"
            ),
            {"now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")},
        )


def downgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch_op:
        batch_op.drop_index(batch_op.f("ix_recurring_expenses_debt_id"))
        batch_op.drop_constraint(batch_op.f("fk_recurring_expenses_debt_id_debts"), type_="foreignkey")
        batch_op.drop_column("debt_id")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_index(batch_op.f("ix_transactions_debt_id"))
        batch_op.drop_constraint(batch_op.f("ck_transactions_debt_only_on_expense"), type_="check")
        batch_op.drop_constraint(batch_op.f("fk_transactions_debt_id_debts"), type_="foreignkey")
        batch_op.drop_column("debt_id")
    op.drop_table("debts")
