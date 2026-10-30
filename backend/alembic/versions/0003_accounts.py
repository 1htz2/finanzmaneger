"""accounts: where savings lie (accounts, account ledger, manual valuations)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 22:56:45.868616
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("institution", sa.String(length=64), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "checking",
                "savings_account",
                "fixed_deposit",
                "brokerage",
                "crypto",
                "cash",
                "other",
                name="account_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("color_index", sa.Integer(), nullable=False),
        sa.Column("savings_share_bp", sa.Integer(), nullable=False),
        sa.Column("holds_reserve", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('checking', 'savings_account', 'fixed_deposit', 'brokerage', 'crypto', 'cash', 'other')",
            name="account_kind",
        ),
        sa.CheckConstraint(
            "kind IN ('checking', 'savings_account', 'fixed_deposit', 'brokerage', 'crypto', 'cash', 'other')",
            name=op.f("ck_accounts_account_kind"),
        ),
        sa.CheckConstraint("color_index >= 0", name=op.f("ck_accounts_color_index_non_negative")),
        sa.CheckConstraint(
            "savings_share_bp >= 0 AND savings_share_bp <= 10000", name=op.f("ck_accounts_share_in_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.create_index(
            "uq_accounts_holds_reserve",
            ["holds_reserve"],
            unique=True,
            sqlite_where=sa.text("holds_reserve = 1"),
        )

    op.create_table(
        "account_valuations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("value_cents", sa.Integer(), nullable=False),
        sa.Column("booked_cents", sa.Integer(), nullable=False),
        sa.Column("valued_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("value_cents >= 0", name=op.f("ck_account_valuations_value_non_negative")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_account_valuations_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_valuations")),
    )
    with op.batch_alter_table("account_valuations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_valuations_account_id"), ["account_id"], unique=False)

    op.create_table(
        "account_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "auto_split",
                "salary_correction",
                "assign",
                "move",
                "income",
                "transfer",
                "withdrawal",
                "reversal",
                name="account_entry_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('auto_split', 'salary_correction', 'assign', 'move', 'income', 'transfer', 'withdrawal', 'reversal')",
            name="account_entry_kind",
        ),
        sa.CheckConstraint(
            "kind IN ('auto_split', 'salary_correction', 'assign', 'move', 'income', 'transfer', 'withdrawal', 'reversal')",
            name=op.f("ck_account_entries_account_entry_kind"),
        ),
        sa.CheckConstraint("amount_cents != 0", name=op.f("ck_account_entries_amount_non_zero")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_account_entries_account_id_accounts")
        ),
        sa.ForeignKeyConstraint(
            ["period_id"], ["budget_periods.id"], name=op.f("fk_account_entries_period_id_budget_periods")
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_account_entries_transaction_id_transactions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_entries")),
    )
    with op.batch_alter_table("account_entries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_entries_account_id"), ["account_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_account_entries_occurred_at"), ["occurred_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_account_entries_period_id"), ["period_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_account_entries_transaction_id"), ["transaction_id"], unique=False
        )
        batch_op.create_index(
            "uq_account_entries_auto_split",
            ["period_id", "account_id"],
            unique=True,
            sqlite_where=sa.text("kind = 'auto_split'"),
        )



def downgrade() -> None:
    with op.batch_alter_table("account_entries", schema=None) as batch_op:
        batch_op.drop_index("uq_account_entries_auto_split", sqlite_where=sa.text("kind = 'auto_split'"))
        batch_op.drop_index(batch_op.f("ix_account_entries_transaction_id"))
        batch_op.drop_index(batch_op.f("ix_account_entries_period_id"))
        batch_op.drop_index(batch_op.f("ix_account_entries_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_account_entries_account_id"))

    op.drop_table("account_entries")
    with op.batch_alter_table("account_valuations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_account_valuations_account_id"))

    op.drop_table("account_valuations")
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_index("uq_accounts_holds_reserve", sqlite_where=sa.text("holds_reserve = 1"))

    op.drop_table("accounts")
