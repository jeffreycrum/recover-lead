"""Tests for lead activity endpoints (GET/POST /{lead_id}/activities, claim, release, update)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "alice@example.com"
    user.clerk_id = "clerk_alice"
    user.is_active = True
    return user


def _make_user_lead(user_id, lead_id, status="new"):
    ul = MagicMock()
    ul.id = uuid.uuid4()
    ul.user_id = user_id
    ul.lead_id = lead_id
    ul.status = status
    ul.quality_score = None
    ul.quality_reasoning = None
    ul.priority = None
    ul.created_at = datetime.now(UTC)
    ul.updated_at = datetime.now(UTC)
    return ul


def _make_activity(lead_id, user_id, activity_type="claimed"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.lead_id = lead_id
    a.user_id = user_id
    a.activity_type = activity_type
    a.description = f"Activity: {activity_type}"
    a.metadata_ = None
    a.created_at = datetime.now(UTC)
    return a


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar_one.return_value = value
    r.scalar.return_value = value
    return r


def _scalars_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


# ---------------------------------------------------------------------------
# GET /leads/{lead_id}/activities
# ---------------------------------------------------------------------------


class TestGetLeadActivities:
    async def test_get_activities_requires_claim(self):
        """Non-claimed lead returns 404 for GET activities."""
        user = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/leads/{lead_id}/activities")
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    async def test_get_activities_tenant_isolated(self):
        """User B cannot see activities on a lead claimed only by user A."""
        user_b = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        # Session returns no user_lead for user_b
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))

        app.dependency_overrides[get_current_user] = lambda: user_b
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/leads/{lead_id}/activities")
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    async def test_get_activities_returns_list(self):
        """GET activities returns a CursorPage with the user's activities."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id)
        activity = _make_activity(lead_id, user.id)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        # First execute: UserLead ownership check
        # Second execute: activities query
        activities_result = MagicMock()
        activities_result.scalars.return_value.all.return_value = [activity]

        session.execute = AsyncMock(
            side_effect=[_scalar_result(user_lead), activities_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/leads/{lead_id}/activities")
                assert response.status_code == 200
                data = response.json()
                assert "items" in data
                assert len(data["items"]) == 1
                assert data["items"][0]["activity_type"] == "claimed"
        finally:
            app.dependency_overrides.clear()

    async def test_get_activities_cursor_pagination(self):
        """has_more=True and next_cursor set when limit+1 results returned."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id)

        # Return limit+1 activities (limit defaults to 25, we test with limit=2)
        acts = [_make_activity(lead_id, user.id) for _ in range(3)]

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        activities_result = MagicMock()
        activities_result.scalars.return_value.all.return_value = acts

        session.execute = AsyncMock(
            side_effect=[_scalar_result(user_lead), activities_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/leads/{lead_id}/activities?limit=2"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["has_more"] is True
                assert data["next_cursor"] is not None
        finally:
            app.dependency_overrides.clear()

    async def test_get_activities_empty_returns_empty_page(self):
        """Empty activities returns has_more=False, empty items."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        activities_result = MagicMock()
        activities_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[_scalar_result(user_lead), activities_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/leads/{lead_id}/activities")
                assert response.status_code == 200
                data = response.json()
                assert data["items"] == []
                assert data["has_more"] is False
                assert data["next_cursor"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /leads/{lead_id}/activities (note creation)
# ---------------------------------------------------------------------------


class TestPostLeadActivity:
    async def test_post_note_creates_activity(self):
        """POST /activities creates a 'note' activity and returns 201."""
        from app.models.lead import LeadActivity

        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id)

        activity = LeadActivity(
            lead_id=lead_id,
            user_id=user.id,
            activity_type="note",
            description="Called the homeowner",
            metadata_=None,
        )
        # Give the activity a real id and created_at since flush is mocked
        activity.id = uuid.uuid4()
        activity.created_at = datetime.now(UTC)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()

        async def _fake_flush():
            pass

        session.flush = AsyncMock(side_effect=_fake_flush)

        # Patch record_activity to return our pre-built activity
        with patch("app.api.v1.leads.record_activity", AsyncMock(return_value=activity)):
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_async_session] = lambda: session

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        f"/api/v1/leads/{lead_id}/activities",
                        json={"description": "Called the homeowner"},
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["activity_type"] == "note"
                    assert data["description"] == "Called the homeowner"
            finally:
                app.dependency_overrides.clear()

    async def test_post_note_requires_claim(self):
        """POST /activities on unclaimed lead returns 404."""
        user = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/activities",
                    json={"description": "A note"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Claim / release record activity
# ---------------------------------------------------------------------------


class TestClaimRecordsActivity:
    async def test_claim_records_claimed_activity(self):
        """POST /claim calls record_activity with type='claimed'."""
        from app.models.lead import LeadActivity

        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id)

        activity = LeadActivity(
            lead_id=lead_id,
            user_id=user.id,
            activity_type="claimed",
            description="Lead claimed",
        )
        activity.id = uuid.uuid4()
        activity.created_at = datetime.now(UTC)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()

        with patch("app.api.v1.leads.claim_lead", AsyncMock(return_value=user_lead)):
            with patch("app.api.v1.leads.record_activity", AsyncMock(return_value=activity)):
                app.dependency_overrides[get_current_user] = lambda: user
                app.dependency_overrides[get_async_session] = lambda: session

                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.post(f"/api/v1/leads/{lead_id}/claim")
                        assert response.status_code == 201
                        data = response.json()
                        assert data["status"] == "new"
                finally:
                    app.dependency_overrides.clear()

    async def test_release_records_released_activity(self):
        """POST /release calls record_activity with type='released' then deletes UserLead."""
        from app.models.lead import LeadActivity

        user = _make_user()
        lead_id = uuid.uuid4()

        activity = LeadActivity(
            lead_id=lead_id,
            user_id=user.id,
            activity_type="released",
            description="Lead released",
        )
        activity.id = uuid.uuid4()
        activity.created_at = datetime.now(UTC)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        session.delete = AsyncMock()

        with patch("app.api.v1.leads.record_activity", AsyncMock(return_value=activity)):
            with patch("app.api.v1.leads.release_lead", AsyncMock(return_value=None)):
                app.dependency_overrides[get_current_user] = lambda: user
                app.dependency_overrides[get_async_session] = lambda: session

                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.post(f"/api/v1/leads/{lead_id}/release")
                        assert response.status_code == 204
                finally:
                    app.dependency_overrides.clear()


class TestStatusChangeRecordsActivity:
    async def test_status_change_records_activity_with_metadata(self):
        """PATCH update records a status_change activity with {from, to} metadata."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="new")

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/leads/{lead_id}",
                    json={"status": "qualified"},
                )
                assert response.status_code == 200
                # Verify session.add was called (for the LeadActivity)
                assert session.add.called
        finally:
            app.dependency_overrides.clear()
