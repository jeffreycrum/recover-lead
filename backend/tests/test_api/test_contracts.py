"""Tests for /contracts API endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.clerk_id = "clerk_test"
    user.is_active = True
    return user


def _make_contract(
    contract_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    status: str = "draft",
    content: str = "Contract content here",
    fee_percentage: Decimal = Decimal("25.00"),
) -> MagicMock:
    c = MagicMock()
    c.id = contract_id or uuid.uuid4()
    c.user_id = user_id or uuid.uuid4()
    c.lead_id = lead_id or uuid.uuid4()
    c.contract_type = "recovery_agreement"
    c.content = content
    c.status = status
    c.fee_percentage = fee_percentage
    c.agent_name = "Test Agent"
    c.created_at = datetime.now(UTC)
    c.updated_at = datetime.now(UTC)
    return c


class TestContractGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_202_with_task_id(self):
        """POST /contracts/generate queues task and returns 202 with task_id."""
        user = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = MagicMock()
        session.execute = AsyncMock(return_value=ul_result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        reservation = MagicMock()
        reservation.allowed = True
        reservation.overage_count = 0
        reservation.period_start_iso = "2026-04-01T00:00:00"

        try:
            with (
                patch(
                    "app.services.billing_service.reserve_usage",
                    new=AsyncMock(return_value=reservation),
                ),
                patch(
                    "app.core.idempotency.get_cached_response",
                    new=AsyncMock(return_value=None),
                ),
                patch("app.core.idempotency.cache_response", new=AsyncMock()),
                patch("app.workers.contract_tasks.generate_contract_task") as mock_task,
                patch("app.core.sse.register_task_owner"),
            ):
                task_result = MagicMock()
                task_result.id = "task-contract-123"
                mock_task.delay.return_value = task_result

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/contracts/generate",
                        json={
                            "lead_id": str(lead_id),
                            "contract_type": "recovery_agreement",
                            "fee_percentage": 25.0,
                            "agent_name": "John Doe",
                        },
                        headers={"Idempotency-Key": str(uuid.uuid4())},
                    )

            assert response.status_code == 202
            data = response.json()
            assert data["task_id"] == "task-contract-123"
            assert data["status"] == "queued"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_generate_returns_404_when_lead_not_claimed(self):
        """POST /contracts/generate returns 404 when lead not claimed by user."""
        user = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=ul_result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/contracts/generate",
                    json={
                        "lead_id": str(lead_id),
                        "fee_percentage": 25.0,
                        "agent_name": "John Doe",
                    },
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_generate_validates_fee_percentage_range(self):
        """POST /contracts/generate rejects fee_percentage outside 0-100."""
        user = _make_user()
        lead_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/contracts/generate",
                    json={
                        "lead_id": str(lead_id),
                        "fee_percentage": 150.0,
                        "agent_name": "John Doe",
                    },
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_generate_returns_401(self):
        """POST /contracts/generate returns 401 without auth token."""
        from fastapi import HTTPException

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        async def override_session():
            yield session

        def raise_401():
            raise HTTPException(status_code=401)

        app.dependency_overrides[get_current_user] = raise_401
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/contracts/generate",
                    json={"lead_id": str(uuid.uuid4()), "fee_percentage": 25.0, "agent_name": "X"},
                )
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


class TestContractList:
    @pytest.mark.asyncio
    async def test_list_returns_user_contracts(self):
        """GET /contracts returns contracts for the authenticated user."""
        user = _make_user()
        contract = _make_contract(user_id=user.id)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()

        row = MagicMock()
        row.Contract = contract
        row.case_number = "TC-2024-001"
        row.owner_name = "Jane Smith"
        row.surplus_amount = Decimal("12000.00")
        row.property_address = "123 Main St"
        row.county_name = "Hillsborough"

        # SQLAlchemy returns tuples: (contract, case_number, owner_name, surplus, addr, county)
        result.all.return_value = [
            (
                contract, "TC-2024-001", "Jane Smith",
                Decimal("12000.00"), "123 Main St", "Hillsborough",
            ),
        ]
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/contracts")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["case_number"] == "TC-2024-001"
            assert data[0]["status"] == "draft"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_tenant_isolation(self):
        """GET /contracts does not return another user's contracts."""
        user_b = _make_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        # User B's session returns empty
        session_b = AsyncMock()
        result_b = MagicMock()
        result_b.all.return_value = []
        session_b.execute = AsyncMock(return_value=result_b)

        async def override_session_b():
            yield session_b

        app.dependency_overrides[get_current_user] = lambda: user_b
        app.dependency_overrides[get_async_session] = override_session_b

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/contracts")

            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()


class TestContractDetail:
    @pytest.mark.asyncio
    async def test_get_contract_returns_404_for_another_users_contract(self):
        """GET /contracts/{id} returns 404 when contract belongs to another user."""
        user = _make_user()
        contract_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/contracts/{contract_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestContractUpdate:
    @pytest.mark.asyncio
    async def test_update_rejects_content_edit_on_approved_contract(self):
        """PATCH /contracts/{id} returns 409 when trying to edit an approved contract."""
        user = _make_user()
        contract = _make_contract(user_id=user.id, status="approved")
        contract_id = contract.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = (
            contract,
            "TC-001",
            "Jane Smith",
            Decimal("5000"),
            "123 Main",
            "Hillsborough",
        )
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/contracts/{contract_id}",
                    json={"content": "Edited content"},
                )
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "NOT_EDITABLE"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_rejects_invalid_status_transition(self):
        """PATCH /contracts/{id} returns 409 for invalid status transition."""
        user = _make_user()
        contract = _make_contract(user_id=user.id, status="draft")
        contract_id = contract.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = (
            contract,
            "TC-001",
            "Jane Smith",
            Decimal("5000"),
            "123 Main",
            "Hillsborough",
        )
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Can't jump from draft directly to signed
                response = await client.patch(
                    f"/api/v1/contracts/{contract_id}",
                    json={"status": "signed"},
                )
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "INVALID_TRANSITION"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_valid_status_transition_draft_to_approved(self):
        """PATCH /contracts/{id} allows draft -> approved transition."""
        user = _make_user()
        contract = _make_contract(user_id=user.id, status="draft")
        contract_id = contract.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = (
            contract,
            "TC-001",
            "Jane Smith",
            Decimal("5000"),
            "123 Main",
            "Hillsborough",
        )
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/contracts/{contract_id}",
                    json={"status": "approved"},
                )
            assert response.status_code == 200
            assert response.json()["status"] == "approved"
        finally:
            app.dependency_overrides.clear()


class TestContractPdf:
    @pytest.mark.asyncio
    async def test_pdf_returns_pdf_content_type(self):
        """GET /contracts/{id}/pdf returns application/pdf with correct header."""
        user = _make_user()
        contract = _make_contract(user_id=user.id)
        contract_id = contract.id
        lead = MagicMock()
        lead.case_number = "TC-2024-001"

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = (contract, "TC-2024-001")
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with patch(
                "app.services.letter_service.generate_pdf",
                return_value=b"%PDF-1.4 fake",
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(f"/api/v1/contracts/{contract_id}/pdf")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert "attachment" in response.headers["content-disposition"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_pdf_returns_404_for_another_users_contract(self):
        """GET /contracts/{id}/pdf returns 404 when contract belongs to another user."""
        user = _make_user()
        contract_id = uuid.uuid4()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/contracts/{contract_id}/pdf")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestContractIdempotency:
    @pytest.mark.asyncio
    async def test_replays_cached_202_without_requeing(self):
        """Second POST /contracts/generate with same Idempotency-Key returns cached 202."""
        user = _make_user()
        lead_id = uuid.uuid4()
        idem_key = str(uuid.uuid4())
        cached_body = {"task_id": "task-cached-abc", "status": "queued", "message": "..."}

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with (
                patch(
                    "app.core.idempotency.get_cached_response",
                    new=AsyncMock(return_value={"status_code": 202, "body": cached_body}),
                ),
                patch("app.workers.contract_tasks.generate_contract_task") as mock_task,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/contracts/generate",
                        json={
                            "lead_id": str(lead_id),
                            "fee_percentage": 25.0,
                            "agent_name": "Jane Doe",
                        },
                        headers={"Idempotency-Key": idem_key},
                    )

            assert response.status_code == 202
            assert response.json()["task_id"] == "task-cached-abc"
            # Task must NOT be queued again on replay
            mock_task.delay.assert_not_called()
        finally:
            app.dependency_overrides.clear()
