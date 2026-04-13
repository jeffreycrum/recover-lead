"""add contact_phone and contact_email to counties

Revision ID: h3g4f5e6d7c8
Revises: g2f3e4d5c6b7
Create Date: 2026-04-13 02:00:00.000000

Adds contact_phone and contact_email columns to the counties table and
populates them from the fl_county_surplus_research.csv data.

These fields surface on county cards in the UI so users can call or email
the clerk's office for counties that require manual data requests.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h3g4f5e6d7c8"
down_revision: str | Sequence[str] | None = "g2f3e4d5c6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, phone, email)  — sourced from fl_county_surplus_research.csv 2026-04-13
CONTACT_DATA: list[tuple[str, str | None, str | None]] = [
    ("Alachua",      None,                              "taxdeeds@alachuaclerk.org"),
    ("Baker",        "(904) 259-8113",                  None),
    ("Bay",          "(850) 747-5729",                  "mnolind@baycoclerk.com"),
    ("Bradford",     "(904) 966-6280",                  None),
    ("Brevard",      "(321) 637-2007",                  "taxdeedclerks@brevardclerk.us"),
    ("Calhoun",      "(850) 674-4545",                  "clerk@calhounclerk.com"),
    ("Charlotte",    "(941) 505-4844",                  None),
    ("Citrus",       "(352) 341-6424",                  "TaxDeeds@CitrusClerk.org"),
    ("Clay",         "(904) 529-4221",                  "taxdeedinfo@clayclerk.com"),
    ("Collier",      "(239) 252-2646",                  None),
    ("Columbia",     "(386) 719-7580",                  None),
    ("DeSoto",       "(863) 993-4876",                  "CustomerService@DesotoClerk.com"),
    ("Dixie",        "(352) 498-1200",                  None),
    ("Duval",        "(904) 255-1916",                  "Ask.Taxdeeds@DuvalClerk.com"),
    ("Escambia",     "(850) 595-3793",                  "taxdeeds@escambiaclerk.com"),
    ("Flagler",      "(386) 313-4375",                  None),
    ("Franklin",     "(850) 653-8861 ext 115",          None),
    ("Gilchrist",    "(352) 463-3170",                  None),
    ("Glades",       "(863) 946-6010",                  "gladesclerk@gladesclerk.com"),
    ("Hamilton",     "(386) 792-1288",                  "godwing@hamiltoncountyfl.com"),
    ("Hardee",       "(863) 773-4174",                  None),
    ("Hendry",       "(863) 675-5217",                  None),
    ("Hernando",     "(352) 540-6772",                  "PublicRecordsRequests@hernandoclerk.org"),
    ("Highlands",    "(863) 402-6586",                  "clkbustd@hcclerk.org"),
    ("Holmes",       "(850) 547-1100",                  None),
    ("Indian River", "(772) 226-3100",                  None),
    ("Jackson",      "(850) 482-9552",                  "clerkmail@jacksonclerk.com"),
    ("Jefferson",    "(850) 342-0218",                  "clerk@jeffersonclerk.com"),
    ("Lafayette",    "(386) 294-1600",                  None),
    ("Lake",         "(352) 253-2620",                  None),
    ("Lee",          None,                              "taxdeedsurplus@leeclerk.org"),
    ("Leon",         "(850) 606-4020",                  "Clerk_TaxDeedAdmin@leoncountyfl.gov"),
    ("Levy",         "(352) 486-5266 x1235",            None),
    ("Liberty",      "(850) 643-2215",                  "info@libertyclerk.com"),
    ("Madison",      "(850) 973-1500",                  "BWashington@MadisonClerk.com"),
    ("Marion",       "(352) 671-5648",                  None),
    ("Martin",       "(772) 288-5554",                  "TaxDeeds@MartinClerk.com"),
    ("Miami-Dade",   "(305) 275-1155",                  None),
    ("Monroe",       "(305) 292-3507",                  "publicrecord@monroe-clerk.com"),
    ("Nassau",       "(904) 548-4604",                  None),
    ("Okaloosa",     "(850) 689-5000",                  "taxdeeds@okaloosaclerk.com"),
    ("Okeechobee",   "(863) 763-2131",                  "thudek@myokeeclerk.com"),
    ("Orange",       "(407) 836-5116",                  None),
    ("Osceola",      "(407) 742-3500",                  None),
    ("Palm Beach",   "(561) 355-2962",                  None),
    ("Pasco",        "(352) 521-4408",                  "taxdeedsurplus@pascoclerk.com"),
    ("Putnam",       "(386) 326-7670",                  "Taxdeeds@putnam-fl.com"),
    ("St. Johns",    "(904) 819-3600",                  "taxdeeds@stjohnsclerk.com"),
    ("St. Lucie",    "(772) 462-6900",                  None),
    ("Sumter",       "(352) 569-6610",                  None),
    ("Suwannee",     "(386) 362-0575",                  "aryellab@suwgov.org"),
    ("Taylor",       "(850) 838-3506 ext 103",          None),
    ("Wakulla",      "(850) 926-0300",                  "receptionist@wakullaclerk.com"),
    ("Walton",       "(850) 892-8115",                  None),
    ("Washington",   "(850) 638-6289",                  None),
]


def upgrade() -> None:
    op.add_column("counties", sa.Column("contact_phone", sa.String(100), nullable=True))
    op.add_column("counties", sa.Column("contact_email", sa.String(255), nullable=True))

    conn = op.get_bind()
    for name, phone, email in CONTACT_DATA:
        conn.execute(
            sa.text(
                "UPDATE counties SET contact_phone = :phone, contact_email = :email "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name, "phone": phone, "email": email},
        )


def downgrade() -> None:
    op.drop_column("counties", "contact_email")
    op.drop_column("counties", "contact_phone")
