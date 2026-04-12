"""Pre-ingest script: scrape all active counties, store leads, generate embeddings.

Run at deploy time to seed initial lead data.

Usage:
    cd backend && python -m scripts.pre_ingest

Or from project root:
    cd backend && python ../scripts/pre_ingest.py
"""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.db.engine import async_session_factory
from app.ingestion.factory import _ensure_scrapers_imported, get_scraper
from app.ingestion.normalizer import normalize_and_store
from app.models.county import County
from app.models.lead import Lead
from app.rag.embeddings import build_lead_text, generate_lead_embedding

_ensure_scrapers_imported()


async def _generate_embeddings(session, county_id: uuid.UUID, county_name: str) -> int:
    """Generate embeddings for leads that don't have them yet."""
    result = await session.execute(
        select(Lead).where(
            Lead.county_id == county_id,
            Lead.embedding.is_(None),
        ).limit(500)
    )
    leads = result.scalars().all()

    count = 0
    for lead in leads:
        text = build_lead_text(
            case_number=lead.case_number,
            owner_name=lead.owner_name,
            property_address=lead.property_address,
            property_city=lead.property_city,
            surplus_amount=float(lead.surplus_amount),
            sale_type=lead.sale_type,
            county_name=county_name,
        )
        lead.embedding = generate_lead_embedding(text)
        count += 1

    if count > 0:
        await session.commit()

    return count


async def scrape_county(county: County, session) -> dict:
    """Scrape a single county and store leads."""
    scraper = get_scraper(county)
    if not scraper:
        return {"county": county.name, "error": f"Unknown scraper: {county.scraper_class}"}

    raw_leads = await scraper.scrape()
    result = await normalize_and_store(session, county.id, raw_leads)

    county.last_scraped_at = datetime.now(UTC).replace(tzinfo=None)
    county.last_lead_count = result["inserted"] + result["skipped"]
    await session.commit()

    # Generate embeddings
    embed_count = await _generate_embeddings(session, county.id, county.name)

    return {
        "county": county.name,
        **result,
        "embeddings": embed_count,
    }


async def main():
    print("=" * 60)
    print("RecoverLead Pre-Ingest: Seeding initial lead data")
    print("=" * 60)

    async with async_session_factory() as session:
        result = await session.execute(
            select(County).where(County.is_active.is_(True))
        )
        counties = result.scalars().all()

        if not counties:
            print("\nNo active counties found. Run seed_counties.py first.")
            return

        print(f"\nFound {len(counties)} active counties.\n")

        results = []
        for county in counties:
            print(f"Scraping {county.name}...", end=" ", flush=True)
            try:
                r = await scrape_county(county, session)
                inserted = r.get('inserted', 0)
                skipped = r.get('skipped', 0)
                embeds = r.get('embeddings', 0)
                print(f"OK - {inserted} new, {skipped} existing, {embeds} embeddings")
                results.append(r)
            except Exception as e:
                print(f"FAILED - {e}")
                results.append({"county": county.name, "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'County':<20} {'Inserted':>10} {'Skipped':>10} {'Embeddings':>12} {'Status':>10}")
    print("-" * 60)
    for r in results:
        if "error" in r:
            print(f"{r['county']:<20} {'':>10} {'':>10} {'':>12} {'FAILED':>10}")
        else:
            ins = r.get('inserted', 0)
            skp = r.get('skipped', 0)
            emb = r.get('embeddings', 0)
            print(f"{r['county']:<20} {ins:>10} {skp:>10} {emb:>12} {'OK':>10}")

    total_inserted = sum(r.get("inserted", 0) for r in results if "error" not in r)
    total_errors = sum(1 for r in results if "error" in r)
    print("-" * 60)
    print(f"Total: {total_inserted} leads inserted, {total_errors} counties failed")


if __name__ == "__main__":
    asyncio.run(main())
