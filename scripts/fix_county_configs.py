"""Fix county configurations in the database."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import update

from app.db.engine import async_session_factory
from app.models.county import County


async def main():
    async with async_session_factory() as session:
        # Fix Hillsborough: was CsvScraper, should be XlsxScraper
        result = await session.execute(
            update(County)
            .where(County.name == "Hillsborough")
            .values(scraper_class="XlsxScraper", source_type="xlsx")
        )
        print(f"Hillsborough → XlsxScraper: {result.rowcount} row(s)")

        # Deactivate broken counties
        for name in ["Broward", "Pinellas", "Polk"]:
            result = await session.execute(
                update(County)
                .where(County.name == name)
                .values(is_active=False)
            )
            print(f"{name} → deactivated: {result.rowcount} row(s)")

        await session.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
