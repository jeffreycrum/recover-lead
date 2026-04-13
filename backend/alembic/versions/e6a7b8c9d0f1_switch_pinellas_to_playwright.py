"""switch pinellas to playwright pdf scraper

Revision ID: e6a7b8c9d0f1
Revises: d5f8a1b2c3e4
Create Date: 2026-04-12 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a7b8c9d0f1"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Pinellas: PDF behind Cloudflare, was 403 with httpx.
    # Switch from PdfScraper to PlaywrightPdfScraper and reactivate.
    op.execute("""
        UPDATE counties
        SET scraper_class = 'PlaywrightPdfScraper',
            is_active = true,
            config = '{"notes": "PDF behind Cloudflare. Uses Playwright to bypass bot protection."}'::jsonb
        WHERE name = 'Pinellas' AND state = 'FL'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE counties
        SET scraper_class = 'PdfScraper',
            is_active = false,
            config = '{"notes": "DEACTIVATED: 403 Cloudflare."}'::jsonb
        WHERE name = 'Pinellas' AND state = 'FL'
    """)
