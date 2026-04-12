"""create pipeline metrics materialized view

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-11 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PIPELINE_METRICS_VIEW_SQL = """
CREATE MATERIALIZED VIEW mv_pipeline_metrics AS
SELECT
    ul.user_id,
    COUNT(*) AS leads_total,
    COUNT(*) FILTER (WHERE ul.status = 'new') AS leads_new,
    COUNT(*) FILTER (WHERE ul.status = 'qualified') AS leads_qualified,
    COUNT(*) FILTER (WHERE ul.status = 'contacted') AS leads_contacted,
    COUNT(*) FILTER (WHERE ul.status = 'signed') AS leads_signed,
    COUNT(*) FILTER (WHERE ul.status = 'filed') AS leads_filed,
    COUNT(*) FILTER (WHERE ul.status = 'paid') AS leads_paid,
    COUNT(*) FILTER (WHERE ul.status = 'closed') AS leads_closed,
    COUNT(*) FILTER (
        WHERE ul.status = 'closed' AND ul.closed_reason = 'recovered'
    ) AS leads_recovered,
    COALESCE(
        SUM(ul.outcome_amount) FILTER (WHERE ul.status IN ('paid', 'closed')),
        0
    ) AS total_recovered,
    COALESCE(
        SUM(ul.fee_amount) FILTER (WHERE ul.status IN ('paid', 'closed')),
        0
    ) AS total_fees,
    AVG(ul.quality_score) AS avg_quality_score,
    MAX(ul.updated_at) AS last_activity_at
FROM user_leads ul
GROUP BY ul.user_id
WITH DATA;
"""


def upgrade() -> None:
    op.execute(PIPELINE_METRICS_VIEW_SQL)
    op.execute(
        "CREATE UNIQUE INDEX ix_mv_pipeline_metrics_user_id ON mv_pipeline_metrics (user_id);"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pipeline_metrics;")
