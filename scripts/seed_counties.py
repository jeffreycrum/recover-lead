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


# Top 10 FL counties by surplus fund volume — active at launch
# Source URLs will need to be verified and updated before scraping
ACTIVE_COUNTIES = [
    {
        "name": "Hillsborough",
        "state": "FL",
        "fips_code": "12057",
        "source_url": "https://www.hillsclerk.com/Portals/0/Documents/Surplus-Funds-List.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Miami-Dade",
        "state": "FL",
        "fips_code": "12086",
        "source_url": "https://www.miamidadeclerk.gov/library/surplus-funds.pdf",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Broward",
        "state": "FL",
        "fips_code": "12011",
        "source_url": "https://www.browardclerk.org/surplus-funds",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Orange",
        "state": "FL",
        "fips_code": "12095",
        "source_url": "https://www.myorangeclerk.com/surplus-funds",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Palm Beach",
        "state": "FL",
        "fips_code": "12099",
        "source_url": "https://www.mypalmbeachclerk.com/surplus-funds",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Pinellas",
        "state": "FL",
        "fips_code": "12103",
        "source_url": "https://www.pinellasclerk.org/surplus-funds",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Duval",
        "state": "FL",
        "fips_code": "12031",
        "source_url": "https://www.duvalclerk.com/surplus-funds",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Lee",
        "state": "FL",
        "fips_code": "12071",
        "source_url": "https://www.leeclerk.org/surplus-funds",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Polk",
        "state": "FL",
        "fips_code": "12105",
        "source_url": "https://www.polkcountyclerk.net/surplus-funds",
        "source_type": "html",
        "scraper_class": "HtmlTableScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
    },
    {
        "name": "Volusia",
        "state": "FL",
        "fips_code": "12127",
        "source_url": "https://www.clerk.org/surplus-funds",
        "source_type": "pdf",
        "scraper_class": "PdfScraper",
        "scrape_schedule": "0 2 * * *",
        "is_active": True,
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
        all_counties = ACTIVE_COUNTIES + INACTIVE_COUNTIES
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
