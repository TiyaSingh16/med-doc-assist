"""add processing_error to documents and sources to chat_messages

Revision ID: b3f1c2d4e5a6
Revises: 1625106311c6
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3f1c2d4e5a6"
down_revision = "1625106311c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Why a document failed (shown to its owner), e.g. "No readable text found".
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    # The excerpts an answer was based on: [{"page": 2, "chunk_index": 5, "excerpt": "..."}]
    op.add_column("chat_messages", sa.Column("sources", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "sources")
    op.drop_column("documents", "processing_error")
