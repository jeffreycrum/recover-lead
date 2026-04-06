"""Seed all 67 Florida county configs. Top 10 by surplus volume set as active."""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session_factory
from app.models.county import County


# Counties with verified, freely accessible surplus fund downloads — active at launch
ACTIVE_COUNTIES = [
    {
        "name": "Volusia",
        "state": "FL",
        "fips_code": "12127",
        "source_url": "https://www.clerk.org/pdf/user_publish/TaxDeeds/Tax_Deed_Surplus_List.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {"notes": "30-page PDF, updated regularly. Main page: https://www.clerk.org/tax-deeds.aspx"},
    },
    {
        "name": "Hillsborough",
        "state": "FL",
        "fips_code": "12057",
        "source_url": "https://www.hillsclerk.com/documents/d/guest/ada-accessible-td-claim-info-master-10-13-2025-2-?download=true",
        "source_type": "csv",
        "scraper_class": "CsvScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {"notes": "Excel/CSV spreadsheet download. Main page: https://hillsclerk.com/taxdeeds"},
    },
    {
        "name": "Pinellas",
        "state": "FL",
        "fips_code": "12103",
        "source_url": "https://mypinellasclerk.gov/Portals/0/Unclaimed%20Monies/2024/508_Unclaimed%20Funds%20Report.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {"notes": "Annual PDF by year. Main page: https://www.mypinellasclerk.gov/Unclaimed-Monies. URL pattern: change year in path."},
    },
    {
        "name": "Broward",
        "state": "FL",
        "fips_code": "12011",
        "source_url": "https://www.broward.org/RecordsTaxesTreasury/TaxesFees/Pages/Overbid.aspx",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {"notes": "Excel/CSV download links on page. Overbid files and surplus disbursements."},
    },
    {
        "name": "Polk",
        "state": "FL",
        "fips_code": "12105",
        "source_url": "https://www.polkclerkfl.gov/280/Surplus-Funds-List",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
        "config": {"notes": "HTML table on page. May 403 to bots — may need browser headers."},
    },
]

# Counties with online data but require custom scraping or contact — inactive for now
PENDING_COUNTIES = [
    {
        "name": "Duval",
        "state": "FL",
        "fips_code": "12031",
        "source_url": "https://www.duvalclerk.com/departments/finance-and-accounting/unclaimed-funds",
        "source_type": "html",
        "scraper_class": None,
        "is_active": False,
        "config": {"notes": "Interactive search only, no bulk download. Tax deed viewer: https://taxdeed.duvalclerk.com/. Contact: Ask.Taxdeeds@DuvalClerk.com"},
    },
    {
        "name": "Lee",
        "state": "FL",
        "fips_code": "12071",
        "source_url": "https://www.leeclerk.org/departments/courts/property-sales/tax-deed-sales/tax-deed-reports",
        "source_type": None,
        "scraper_class": None,
        "is_active": False,
        "config": {"notes": "Weekly reports may be available. Contact: taxdeedsurplus@leeclerk.org"},
    },
    {
        "name": "Miami-Dade",
        "state": "FL",
        "fips_code": "12086",
        "source_url": "https://www.miamidadeclerk.gov/clerk/property-tax-deeds.page",
        "source_type": None,
        "scraper_class": None,
        "is_active": False,
        "config": {"notes": "No public surplus list. Must contact Foreclosure Unit at 305-275-1155."},
    },
    {
        "name": "Palm Beach",
        "state": "FL",
        "fips_code": "12099",
        "source_url": "https://www.mypalmbeachclerk.com/departments/courts/tax-deeds/sale-information",
        "source_type": None,
        "scraper_class": None,
        "is_active": False,
        "config": {"notes": "Surplus report must be purchased from Clerk Cart. Contact: 561-355-2962."},
    },
    {
        "name": "Orange",
        "state": "FL",
        "fips_code": "12095",
        "source_url": "https://www.occompt.com/191/Tax-Deed-Sales",
        "source_type": None,
        "scraper_class": None,
        "is_active": False,
        "config": {"notes": "No public surplus list. Unclaimed property sent to state: https://www.fltreasurehunt.gov/. Contact: 407-836-5116."},
    },
]

# Remaining 57 FL counties — seeded as inactive (no scraper configured yet)
INACTIVE_COUNTIES = [
    {"name": n, "state": "FL", "fips_code": f, "is_active": False}
    for n, f in [
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
]


async def seed():
    """Seed all FL counties into the database."""
    async with async_session_factory() as session:
        all_counties = ACTIVE_COUNTIES + PENDING_COUNTIES + INACTIVE_COUNTIES
        inserted = 0
        skipped = 0

        for county_data in all_counties:
            # Check if exists
            result = await session.execute(
                select(County).where(
                    County.name == county_data["name"],
                    County.state == county_data["state"],
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update if active status changed
                if existing.is_active != county_data.get("is_active", False):
                    existing.is_active = county_data.get("is_active", False)
                if county_data.get("source_url") and not existing.source_url:
                    existing.source_url = county_data.get("source_url")
                    existing.source_type = county_data.get("source_type")
                    existing.scraper_class = county_data.get("scraper_class")
                    existing.scrape_schedule = county_data.get("scrape_schedule")
                skipped += 1
                continue

            county = County(**county_data)
            session.add(county)
            inserted += 1

        await session.commit()
        print(f"Seeded {inserted} counties, skipped {skipped} existing.")
        print(f"Active: {sum(1 for c in all_counties if c.get('is_active', False))}")
        print(f"Inactive: {sum(1 for c in all_counties if not c.get('is_active', False))}")


if __name__ == "__main__":
    asyncio.run(seed())
