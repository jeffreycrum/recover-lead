"""seed florida counties

Revision ID: d5f8a1b2c3e4
Revises: c11033abbf71
Create Date: 2026-04-09 17:00:00.000000

"""

from typing import Sequence

import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d5f8a1b2c3e4"
down_revision: str | Sequence[str] | None = "c11033abbf71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Counties table reference
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
    sa.column("config", sa.JSON),
)

ACTIVE_COUNTIES = [
    {
        "name": "Volusia",
        "fips_code": "12127",
        "source_url": "https://www.clerk.org/pdf/user_publish/TaxDeeds/Tax_Deed_Surplus_List.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {
            "notes": "30-page PDF, updated regularly.",
            "columns": {"case_number": 2, "owner_name": 1, "surplus_amount": 3, "property_address": None},
            "skip_rows_containing": ["CLERK OF THE CIRCUIT", "TAX DEED SURPLUS", "Fee calculator", "Deposit amount", "Date Surplus", "Amt of Deposit"],
        },
    },
    {
        "name": "Hillsborough",
        "fips_code": "12057",
        "source_url": "https://www.hillsclerk.com/documents/d/guest/ada-accessible-td-claim-info-master-10-13-2025-2-?download=true",
        "source_type": "xlsx",
        "scraper_class": "XlsxScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {
            "notes": "Excel spreadsheet. Claims tracking format.",
            "column_mapping": {"case_number": 0, "owner_name": 1, "surplus_amount": 1},
            "extract_from_claims": True,
        },
    },
    {
        "name": "Pinellas",
        "fips_code": "12103",
        "source_url": "https://mypinellasclerk.gov/Portals/0/Unclaimed%20Monies/2024/508_Unclaimed%20Funds%20Report.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": False,
        "config": {"notes": "DEACTIVATED: 403 Cloudflare."},
    },
    {
        "name": "Broward",
        "fips_code": "12011",
        "source_url": "https://www.broward.org/RecordsTaxesTreasury/TaxesFees/Pages/Overbid.aspx",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": False,
        "config": {"notes": "DEACTIVATED: 404."},
    },
    {
        "name": "Polk",
        "fips_code": "12105",
        "source_url": "https://www.polkclerkfl.gov/280/Surplus-Funds-List",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": False,
        "config": {"notes": "DEACTIVATED: 404. Site restructured."},
    },
]

PENDING_COUNTIES = [
    {"name": "Duval", "fips_code": "12031", "source_url": "https://www.duvalclerk.com/departments/finance-and-accounting/unclaimed-funds", "source_type": "html", "config": {"notes": "Interactive search only. Contact: Ask.Taxdeeds@DuvalClerk.com"}},
    {"name": "Lee", "fips_code": "12071", "source_url": "https://www.leeclerk.org/departments/courts/property-sales/tax-deed-sales/tax-deed-reports", "config": {"notes": "Contact: taxdeedsurplus@leeclerk.org"}},
    {"name": "Miami-Dade", "fips_code": "12086", "source_url": "https://www.miamidadeclerk.gov/clerk/property-tax-deeds.page", "config": {"notes": "Contact Foreclosure Unit: 305-275-1155."}},
    {"name": "Palm Beach", "fips_code": "12099", "source_url": "https://www.mypalmbeachclerk.com/departments/courts/tax-deeds/sale-information", "config": {"notes": "Surplus report from Clerk Cart. Contact: 561-355-2962."}},
    {"name": "Orange", "fips_code": "12095", "source_url": "https://www.occompt.com/191/Tax-Deed-Sales", "config": {"notes": "Unclaimed property sent to state. Contact: 407-836-5116."}},
]

INACTIVE_COUNTIES = [
    ("Alachua", "12001"), ("Baker", "12003"), ("Bay", "12005"),
    ("Bradford", "12007"), ("Brevard", "12009"), ("Calhoun", "12013"),
    ("Charlotte", "12015"), ("Citrus", "12017"), ("Clay", "12019"),
    ("Collier", "12021"), ("Columbia", "12023"), ("DeSoto", "12027"),
    ("Dixie", "12029"), ("Escambia", "12033"), ("Flagler", "12035"),
    ("Franklin", "12037"), ("Gadsden", "12039"), ("Gilchrist", "12041"),
    ("Glades", "12043"), ("Gulf", "12045"), ("Hamilton", "12047"),
    ("Hardee", "12049"), ("Hendry", "12051"), ("Hernando", "12053"),
    ("Highlands", "12055"), ("Holmes", "12059"), ("Indian River", "12061"),
    ("Jackson", "12063"), ("Jefferson", "12065"), ("Lafayette", "12067"),
    ("Lake", "12069"), ("Leon", "12073"), ("Levy", "12075"),
    ("Liberty", "12077"), ("Madison", "12079"), ("Manatee", "12081"),
    ("Marion", "12083"), ("Martin", "12085"), ("Monroe", "12087"),
    ("Nassau", "12089"), ("Okaloosa", "12091"), ("Okeechobee", "12093"),
    ("Osceola", "12097"), ("Pasco", "12101"), ("Putnam", "12107"),
    ("Santa Rosa", "12113"), ("Sarasota", "12115"), ("Seminole", "12117"),
    ("St. Johns", "12109"), ("St. Lucie", "12111"), ("Sumter", "12119"),
    ("Suwannee", "12121"), ("Taylor", "12123"), ("Union", "12125"),
    ("Wakulla", "12129"), ("Walton", "12131"), ("Washington", "12133"),
]


def upgrade() -> None:
    rows = []

    for c in ACTIVE_COUNTIES:
        rows.append({
            "id": uuid.uuid4(),
            "name": c["name"],
            "state": "FL",
            "fips_code": c.get("fips_code"),
            "source_url": c.get("source_url"),
            "source_type": c.get("source_type"),
            "scraper_class": c.get("scraper_class"),
            "scrape_schedule": c.get("scrape_schedule"),
            "is_active": c.get("is_active", False),
            "config": c.get("config"),
        })

    for c in PENDING_COUNTIES:
        rows.append({
            "id": uuid.uuid4(),
            "name": c["name"],
            "state": "FL",
            "fips_code": c.get("fips_code"),
            "source_url": c.get("source_url"),
            "source_type": c.get("source_type"),
            "scraper_class": None,
            "scrape_schedule": None,
            "is_active": False,
            "config": c.get("config"),
        })

    for name, fips in INACTIVE_COUNTIES:
        rows.append({
            "id": uuid.uuid4(),
            "name": name,
            "state": "FL",
            "fips_code": fips,
            "source_url": None,
            "source_type": None,
            "scraper_class": None,
            "scrape_schedule": None,
            "is_active": False,
            "config": None,
        })

    op.bulk_insert(counties, rows)


def downgrade() -> None:
    op.execute("DELETE FROM counties WHERE state = 'FL'")
