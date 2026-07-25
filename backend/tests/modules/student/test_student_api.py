"""
Student REST API Integration Tests — Phase 4 Step 2.

Tests all 6 endpoints:
  POST   /api/v1/students
  GET    /api/v1/students
  GET    /api/v1/students/{id}
  PUT    /api/v1/students/{id}
  DELETE /api/v1/students/{id}
  POST   /api/v1/students/{id}/restore

Coverage:
  ✓ Create Student (201)
  ✓ Duplicate Admission Number (409)
  ✓ Validation Error (422)
  ✓ Unauthorized (401)
  ✓ Get Student (200)
  ✓ Get Student Not Found (404)
  ✓ List Students with Pagination
  ✓ List Students with Search
  ✓ List Students with Status Filter
  ✓ Update Student (200)
  ✓ Delete Student — Soft Delete (200)
  ✓ Restore Student (200)
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User

BASE_URL = "/api/v1/students"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Creates a SUPER_ADMIN test user, logs in, returns Authorization headers."""
    async with AsyncSessionLocal() as session:
        school_res = await session.execute(select(School).limit(1))
        school = school_res.scalar_one()

        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"api_test_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apitest_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="API",
            last_name="Tester",
            username=username,
            email=email,
            password_hash=hash_password(pwd),
            school_id=school.id,
            role_id=role.id,
            status="active",
            email_verified=True,
        )
        session.add(user)
        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]

    yield {"Authorization": f"Bearer {token}"}

    # Cleanup user
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User).where(User.email == email))
        u = user_res.scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


@pytest.fixture
async def school_id() -> uuid.UUID:
    """Returns the UUID of the first seeded school."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(School).limit(1))
        school = res.scalar_one()
        return school.id


def _student_payload(school_id: uuid.UUID, **overrides) -> dict:
    """Returns a base-valid student creation payload dict."""
    payload = {
        "school_id": str(school_id),
        "admission_number": f"ADM_{uuid.uuid4().hex[:8]}",
        "first_name": "Integration",
        "last_name": "Test",
        "gender": "MALE",
        "date_of_birth": "2015-06-15",
        "joined_date": str(date.today() - timedelta(days=30)),
        "status": "NEW",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# POST /students — Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_student_success(client: AsyncClient, auth_headers: dict, school_id: uuid.UUID):
    """POST /students returns 201 on valid payload."""
    payload = _student_payload(school_id)
    resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["admission_number"] == payload["admission_number"]
    assert data["data"]["status"] == "NEW"


@pytest.mark.asyncio
async def test_create_student_duplicate_admission_number(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """POST /students returns 409 on duplicate admission number."""
    adm_no = f"ADM_{uuid.uuid4().hex[:8]}"
    payload = _student_payload(school_id, admission_number=adm_no)

    resp1 = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_student_validation_error(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """POST /students returns 422 when required field is missing."""
    # Missing first_name
    payload = _student_payload(school_id)
    payload.pop("first_name")
    resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_student_unauthorized(client: AsyncClient, school_id: uuid.UUID):
    """POST /students returns 401 without auth token."""
    payload = _student_payload(school_id)
    resp = await client.post(BASE_URL + "/", json=payload)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /students/{id} — Get Single
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_student_success(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """GET /students/{id} returns 200 with StudentResponse."""
    # First create
    payload = _student_payload(school_id)
    create_resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    student_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(f"{BASE_URL}/{student_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == student_id


@pytest.mark.asyncio
async def test_get_student_not_found(client: AsyncClient, auth_headers: dict):
    """GET /students/{id} returns 404 for non-existent UUID."""
    resp = await client.get(f"{BASE_URL}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /students — List with Pagination, Search, Filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_students_pagination(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """GET /students?page=1&page_size=5 returns paginated response."""
    resp = await client.get(f"{BASE_URL}/?page=1&page_size=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "pagination" in data
    assert "results" in data
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 5


@pytest.mark.asyncio
async def test_list_students_search(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """GET /students?search=<name> returns only matching results."""
    unique_name = f"Searchable_{uuid.uuid4().hex[:6]}"
    payload = _student_payload(school_id, first_name=unique_name)
    create_resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201

    search_resp = await client.get(
        f"{BASE_URL}/?search={unique_name}", headers=auth_headers
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert len(results) >= 1
    assert any(r["first_name"] == unique_name for r in results)


@pytest.mark.asyncio
async def test_list_students_filter_by_status(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """GET /students?status=NEW returns only NEW status students."""
    # Create a student with NEW status (default)
    payload = _student_payload(school_id)
    resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    list_resp = await client.get(f"{BASE_URL}/?status=NEW", headers=auth_headers)
    assert list_resp.status_code == 200
    results = list_resp.json()["results"]
    assert all(r["status"] == "NEW" for r in results)


# ---------------------------------------------------------------------------
# PUT /students/{id} — Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_student_success(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """PUT /students/{id} returns 200 with updated fields."""
    payload = _student_payload(school_id)
    create_resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    student_id = create_resp.json()["data"]["id"]

    update_resp = await client.put(
        f"{BASE_URL}/{student_id}",
        json={"first_name": "Updated", "status": "ACTIVE"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["data"]["first_name"] == "Updated"
    assert data["data"]["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# DELETE /students/{id} — Soft Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_student_success(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """DELETE /students/{id} returns 200 and hides the record from GET."""
    payload = _student_payload(school_id)
    create_resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    student_id = create_resp.json()["data"]["id"]

    del_resp = await client.delete(f"{BASE_URL}/{student_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Soft deleted — GET should now return 404
    get_resp = await client.get(f"{BASE_URL}/{student_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /students/{id}/restore — Restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_student_success(
    client: AsyncClient, auth_headers: dict, school_id: uuid.UUID
):
    """POST /students/{id}/restore returns 200 and makes record accessible again."""
    payload = _student_payload(school_id)
    create_resp = await client.post(BASE_URL + "/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    student_id = create_resp.json()["data"]["id"]

    # Soft delete
    del_resp = await client.delete(f"{BASE_URL}/{student_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Restore
    restore_resp = await client.post(
        f"{BASE_URL}/{student_id}/restore", headers=auth_headers
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["success"] is True

    # Should be accessible again
    get_resp = await client.get(f"{BASE_URL}/{student_id}", headers=auth_headers)
    assert get_resp.status_code == 200
