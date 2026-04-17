"""seed state-specific letter templates for TX, OH, CA, GA

Revision ID: y0z1a2b3c4d5
Revises: x0y1z2a3b4c5
Create Date: 2026-04-15 10:00:00.000000

Inserts one default LetterTemplate row per state for the four non-FL states
that have activated scrapers. Template bodies are rendered from the .j2 files
in app/templates/ and stored here so they are visible in admin/future UI.
The letter generator reads templates from the .j2 files at runtime; these
rows are informational and for future UI display.
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "y0z1a2b3c4d5"
down_revision = "x0y1z2a3b4c5"
branch_labels = None
depends_on = None

_TEMPLATES = [
    {
        "state": "TX",
        "letter_type": "excess_proceeds",
        "name": "Texas Excess Proceeds",
    },
    {
        "state": "OH",
        "letter_type": "excess_proceeds",
        "name": "Ohio Excess Proceeds",
    },
    {
        "state": "CA",
        "letter_type": "excess_proceeds",
        "name": "California Excess Proceeds",
    },
    {
        "state": "GA",
        "letter_type": "excess_proceeds",
        "name": "Georgia Excess Proceeds",
    },
]

# Placeholder body stored in the DB row. The live template is rendered from
# app/templates/<state>_excess_proceeds.j2 at letter-generation time.
_BODY_PLACEHOLDER = "(Rendered from app/templates/{state}_excess_proceeds.j2)"


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(tz=UTC)
    for tmpl in _TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO letter_templates
                    (id, name, letter_type, template_body, state, is_default, created_at)
                VALUES
                    (:id, :name, :letter_type, :template_body, :state, :is_default, :created_at)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": tmpl["name"],
                "letter_type": tmpl["letter_type"],
                "template_body": _BODY_PLACEHOLDER.format(state=tmpl["state"].lower()),
                "state": tmpl["state"],
                "is_default": True,
                "created_at": now,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for tmpl in _TEMPLATES:
        conn.execute(
            sa.text(
                "DELETE FROM letter_templates"
                " WHERE state = :state AND letter_type = :letter_type AND is_default = TRUE"
            ),
            {"state": tmpl["state"], "letter_type": tmpl["letter_type"]},
        )
