import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def find_similar_leads(
    session: AsyncSession,
    embedding: list[float],
    county_id: uuid.UUID | None = None,
    limit: int = 5,
    exclude_lead_id: uuid.UUID | None = None,
) -> list[dict]:
    """Find similar leads using pgvector cosine distance.

    Raw pgvector query — no LlamaIndex wrapper needed for this.
    """
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    # Build query with optional filters
    conditions = ["embedding IS NOT NULL"]
    params: dict = {"embedding": embedding_str, "limit": limit}

    if county_id:
        conditions.append("county_id = :county_id")
        params["county_id"] = str(county_id)

    if exclude_lead_id:
        conditions.append("id != :exclude_id")
        params["exclude_id"] = str(exclude_lead_id)

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT id, case_number, owner_name, surplus_amount, sale_type,
               property_address, property_city,
               embedding <=> :embedding::vector AS distance
        FROM leads
        WHERE {where_clause}
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    return [
        {
            "id": str(row.id),
            "case_number": row.case_number,
            "owner_name": row.owner_name,
            "surplus_amount": float(row.surplus_amount) if row.surplus_amount else 0,
            "sale_type": row.sale_type,
            "property_address": row.property_address,
            "property_city": row.property_city,
            "distance": float(row.distance),
        }
        for row in rows
    ]
