"""seed ohio counties

Revision ID: w9x0y1z2a3b4
Revises: p2q3r4s5t6u7
Create Date: 2026-04-14 12:00:00.000000

Seeds all 88 Ohio counties into the counties table with is_active=False.

Ohio surplus fund legal basis:
  - ORC § 5721.19: excess proceeds from judicial tax foreclosure sales
  - ORC § 5723: forfeited land sales (auditor-initiated)
  - Proceeds held by County Treasurer; claims filed as court motions
  - 90-day claim window from sale confirmation order (ORC § 5721.19(D))
  - Unclaimed funds transfer to county general fund after 90 days

Key findings from initial research (2026-04-14):
  - GovEase platform NOT used by any Ohio county (Ohio not on GovEase)
  - Most Ohio counties do NOT publish public excess proceeds lists online
  - Exception: Cuyahoga (Cleveland) — direct XLSX downloads on clerk page
  - Hamilton (Cincinnati) — PDF on courtclerk.org (may require browser fetch)
  - Montgomery (Dayton) — PDF on mcclerkofcourts.org (possibly image-based)
  - Lucas (Toledo) — JPG image only (OCR required, not machine-readable)
  - Franklin, Summit, Stark, Warren — no public list found
  - Butler — excess proceeds list gated behind Nextcloud auth

Activation handled in x0y1z2a3b4c5_activate_ohio_counties.py.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "w9x0y1z2a3b4"
down_revision: str | Sequence[str] | None = "p2q3r4s5t6u7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

counties = sa.table(
    "counties",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("state", sa.String),
    sa.column("fips_code", sa.String),
    sa.column("source_url", sa.String),
    sa.column("source_type", sa.String),
    sa.column("scraper_class", sa.String),
    sa.column("scrape_schedule", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("last_lead_count", sa.Integer),
    sa.column("config", sa.JSON),
)

# All 88 Ohio counties: (name, fips_code)
# FIPS codes: 39001–39175, odd increments (alphabetical order)
_OH_COUNTIES = [
    ("Adams", "39001"),
    ("Allen", "39003"),
    ("Ashland", "39005"),
    ("Ashtabula", "39007"),
    ("Athens", "39009"),
    ("Auglaize", "39011"),
    ("Belmont", "39013"),
    ("Brown", "39015"),
    ("Butler", "39017"),
    ("Carroll", "39019"),
    ("Champaign", "39021"),
    ("Clark", "39023"),
    ("Clermont", "39025"),
    ("Clinton", "39027"),
    ("Columbiana", "39029"),
    ("Coshocton", "39031"),
    ("Crawford", "39033"),
    ("Cuyahoga", "39035"),
    ("Darke", "39037"),
    ("Defiance", "39039"),
    ("Delaware", "39041"),
    ("Erie", "39043"),
    ("Fairfield", "39045"),
    ("Fayette", "39047"),
    ("Franklin", "39049"),
    ("Fulton", "39051"),
    ("Gallia", "39053"),
    ("Geauga", "39055"),
    ("Greene", "39057"),
    ("Guernsey", "39059"),
    ("Hamilton", "39061"),
    ("Hancock", "39063"),
    ("Hardin", "39065"),
    ("Harrison", "39067"),
    ("Henry", "39069"),
    ("Highland", "39071"),
    ("Hocking", "39073"),
    ("Holmes", "39075"),
    ("Huron", "39077"),
    ("Jackson", "39079"),
    ("Jefferson", "39081"),
    ("Knox", "39083"),
    ("Lake", "39085"),
    ("Lawrence", "39087"),
    ("Licking", "39089"),
    ("Logan", "39091"),
    ("Lorain", "39093"),
    ("Lucas", "39095"),
    ("Madison", "39097"),
    ("Mahoning", "39099"),
    ("Marion", "39101"),
    ("Medina", "39103"),
    ("Meigs", "39105"),
    ("Mercer", "39107"),
    ("Miami", "39109"),
    ("Monroe", "39111"),
    ("Montgomery", "39113"),
    ("Morgan", "39115"),
    ("Morrow", "39117"),
    ("Muskingum", "39119"),
    ("Noble", "39121"),
    ("Ottawa", "39123"),
    ("Paulding", "39125"),
    ("Perry", "39127"),
    ("Pickaway", "39129"),
    ("Pike", "39131"),
    ("Portage", "39133"),
    ("Preble", "39135"),
    ("Putnam", "39137"),
    ("Richland", "39139"),
    ("Ross", "39141"),
    ("Sandusky", "39143"),
    ("Scioto", "39145"),
    ("Seneca", "39147"),
    ("Shelby", "39149"),
    ("Stark", "39151"),
    ("Summit", "39153"),
    ("Trumbull", "39155"),
    ("Tuscarawas", "39157"),
    ("Union", "39159"),
    ("Van Wert", "39161"),
    ("Vinton", "39163"),
    ("Warren", "39165"),
    ("Washington", "39167"),
    ("Wayne", "39169"),
    ("Williams", "39171"),
    ("Wood", "39173"),
    ("Wyandot", "39175"),
]


def upgrade() -> None:
    rows = [
        {
            "id": uuid.uuid4(),
            "name": name,
            "state": "OH",
            "fips_code": fips,
            "source_url": None,
            "source_type": None,
            "scraper_class": None,
            "scrape_schedule": None,
            "is_active": False,
            "last_lead_count": 0,
            "config": None,
        }
        for name, fips in _OH_COUNTIES
    ]
    op.bulk_insert(counties, rows)


def downgrade() -> None:
    op.execute("DELETE FROM counties WHERE state = 'OH'")
