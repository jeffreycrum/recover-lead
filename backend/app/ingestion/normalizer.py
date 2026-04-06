import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base_scraper import RawLead, compute_source_hash
from app.models.lead import Lead

logger = structlog.get_logger()


async def normalize_and_store(
    session: AsyncSession,
    county_id: uuid.UUID,
    raw_leads: list[RawLead],
) -> dict[str, int]:
    """Normalize raw leads and upsert into the database. Returns counts."""
    inserted = 0
    skipped = 0
    errors = 0

    for raw in raw_leads:
        try:
            source_hash = compute_source_hash(
                str(county_id),
                raw.case_number,
                raw.parcel_id,
                raw.owner_name,
            )

            # Check for existing lead by (county_id, case_number)
            result = await session.execute(
                select(Lead).where(
                    Lead.county_id == county_id,
                    Lead.case_number == raw.case_number,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update if source data changed
                if existing.source_hash != source_hash:
                    existing.surplus_amount = raw.surplus_amount
                    existing.owner_name = raw.owner_name
                    existing.owner_last_known_address = raw.owner_last_known_address
                    existing.property_address = raw.property_address
                    existing.property_city = raw.property_city
                    existing.property_zip = raw.property_zip
                    existing.source_hash = source_hash
                    existing.raw_data = raw.raw_data
                    inserted += 1
                else:
                    skipped += 1
                continue

            # Parse sale_date
            sale_date = None
            if raw.sale_date:
                try:
                    sale_date = date.fromisoformat(raw.sale_date)
                except ValueError:
                    pass

            lead = Lead(
                county_id=county_id,
                case_number=raw.case_number,
                parcel_id=raw.parcel_id,
                property_address=raw.property_address,
                property_city=raw.property_city,
                property_state=raw.property_state,
                property_zip=raw.property_zip,
                surplus_amount=raw.surplus_amount,
                sale_date=sale_date,
                sale_type=raw.sale_type,
                owner_name=raw.owner_name,
                owner_last_known_address=raw.owner_last_known_address,
                source_hash=source_hash,
                raw_data=raw.raw_data,
            )
            session.add(lead)
            inserted += 1

        except Exception as e:
            logger.error("lead_normalize_failed", case_number=raw.case_number, error=str(e))
            errors += 1

    await session.flush()

    result = {"inserted": inserted, "skipped": skipped, "errors": errors, "total": len(raw_leads)}
    logger.info("normalize_complete", county_id=str(county_id), **result)
    return result
