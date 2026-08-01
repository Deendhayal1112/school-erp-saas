import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.department.models import Department
from app.modules.room.enums import RoomType
from app.modules.room.exceptions import (
    DuplicateBuildingException,
    DuplicateFloorException,
    InvalidCapacityException,
    InvalidFloorBelongingException,
)
from app.modules.room.models import (
    Building,
    Floor,
    Room,
    RoomAllocationRule,
    RoomFacility,
)
from app.modules.room.service import RoomService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def room_fixtures():
    """Seeds database with schools, departments, users, and roles for room testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Room Test",
            code=f"RM1_{uuid.uuid4().hex[:6]}",
            email=f"rm1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Room Test",
            code=f"RM2_{uuid.uuid4().hex[:6]}",
            email=f"rm2_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Seed SUPER_ADMIN and TEACHER roles
        sa_role_res = await session.execute(
            select(Role).where(Role.code == "SUPER_ADMIN")
        )
        sa_role = sa_role_res.scalar_one()

        t_role_res = await session.execute(select(Role).where(Role.code == "TEACHER"))
        t_role = t_role_res.scalar_one()

        # Create Departments
        dept1 = Department(
            school_id=school1.id,
            department_name="Science Department Apex",
            department_code=f"SCI_{uuid.uuid4().hex[:4]}",
            display_name="Apex Science",
            is_active=True,
        )
        dept2 = Department(
            school_id=school2.id,
            department_name="Science Department Summit",
            department_code=f"SCI_{uuid.uuid4().hex[:4]}",
            display_name="Summit Science",
            is_active=True,
        )
        session.add_all([dept1, dept2])
        await session.commit()
        await session.refresh(dept1)
        await session.refresh(dept2)

        # Seed Users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"rm_admin1_{rand_id}",
            email=f"rm_admin1_{rand_id}@school1.edu",
            phone=f"+91810000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="Admin",
            username=f"rm_admin2_{rand_id}",
            email=f"rm_admin2_{rand_id}@school2.edu",
            phone=f"+91910000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        t_user = User(
            first_name="Teacher",
            last_name="User",
            username=f"rm_teacher_{rand_id}",
            email=f"rm_teacher_{rand_id}@school1.edu",
            phone=f"+91820000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=t_role.id,
        )
        session.add_all([u1, u2, t_user])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        await session.refresh(t_user)

        yield school1, school2, u1, u2, t_user, dept1, dept2

        # Cleanup
        async with AsyncSessionLocal() as session_cleanup:
            # Delete room records manually if cascading isn't dynamic in tests
            await session_cleanup.execute(
                delete(RoomAllocationRule).where(
                    RoomAllocationRule.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(RoomFacility).where(
                    RoomFacility.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(Room).where(Room.school_id.in_([school1.id, school2.id]))
            )
            await session_cleanup.execute(
                delete(Floor).where(Floor.school_id.in_([school1.id, school2.id]))
            )
            await session_cleanup.execute(
                delete(Building).where(Building.school_id.in_([school1.id, school2.id]))
            )
            await session_cleanup.execute(
                delete(Department).where(
                    Department.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(User).where(User.id.in_([u1.id, u2.id, t_user.id]))
            )
            await session_cleanup.execute(
                delete(School).where(School.id.in_([school1.id, school2.id]))
            )
            await session_cleanup.commit()


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# SERVICE & VALIDATION TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_room_validation_rules(room_fixtures):
    school1, _, u1, _, _, _dept1, _ = room_fixtures

    async with AsyncSessionLocal() as session:
        service = RoomService(session)

        # 1. Duplicate building code
        from pydantic import ValidationError

        from app.modules.room.schemas import BuildingCreate, FloorCreate, RoomCreate

        b_data = BuildingCreate(
            building_code="B1",
            building_name="Block One",
            number_of_floors=3,
        )
        b1 = await service.create_building(school1.id, b_data, u1)

        with pytest.raises(DuplicateBuildingException):
            await service.create_building(school1.id, b_data, u1)

        # 2. Duplicate floor number in building
        fl_data = FloorCreate(
            building_id=b1.id,
            floor_number=1,
            floor_name="First Floor",
        )
        fl1 = await service.create_floor(school1.id, fl_data, u1)

        with pytest.raises(DuplicateFloorException):
            await service.create_floor(school1.id, fl_data, u1)

        # 3. Invalid Floor Belonging validation
        other_b_data = BuildingCreate(
            building_code="B2",
            building_name="Block Two",
            number_of_floors=2,
        )
        b2 = await service.create_building(school1.id, other_b_data, u1)

        # Room belongs to building B1 but we claim floor is in building B2
        fl_data2 = FloorCreate(
            building_id=b2.id,
            floor_number=1,
            floor_name="First Floor Block 2",
        )
        fl2 = await service.create_floor(school1.id, fl_data2, u1)

        r_data = RoomCreate(
            building_id=b1.id,
            floor_id=fl2.id,  # Floor belonging to b2
            room_code="R101",
            room_name="Room 101",
            room_type=RoomType.CLASSROOM,
            capacity=40,
            available_capacity=40,
        )

        with pytest.raises(InvalidFloorBelongingException):
            await service.create_room(school1.id, r_data, u1)

        # 4. Invalid Capacity limits (capacity <= 0 or available_capacity > capacity)
        with pytest.raises(ValidationError):
            RoomCreate(
                building_id=b1.id,
                floor_id=fl1.id,
                room_code="R101_INV",
                room_name="Room 101 Invalid",
                room_type=RoomType.CLASSROOM,
                capacity=0,
                available_capacity=0,
            )

        r_invalid_avail = RoomCreate(
            building_id=b1.id,
            floor_id=fl1.id,
            room_code="R101_INV2",
            room_name="Room 101 Invalid",
            room_type=RoomType.CLASSROOM,
            capacity=40,
            available_capacity=50,
        )
        with pytest.raises(InvalidCapacityException):
            await service.create_room(school1.id, r_invalid_avail, u1)


# ===========================================================================
# API ENDPOINT & TENANT ISOLATION & RBAC TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_room_api_lifecycle(client: AsyncClient, room_fixtures):
    _school1, _school2, u1, u2, t_user, dept1, dept2 = room_fixtures

    headers1 = await get_auth_headers(client, u1.email)
    headers2 = await get_auth_headers(client, u2.email)
    t_headers = await get_auth_headers(client, t_user.email)

    # 1. Create Building
    b_payload = {
        "building_code": "BLDG-X",
        "building_name": "Block X",
        "description": "Science Block",
        "address": "South Zone",
        "number_of_floors": 4,
        "status": "ACTIVE",
    }
    b_resp = await client.post("/api/v1/buildings", json=b_payload, headers=headers1)
    assert b_resp.status_code == 201, b_resp.text
    b_id = b_resp.json()["data"]["id"]

    # Tenant check: school 2 shouldn't see this building
    b_get_fail = await client.get(f"/api/v1/buildings/{b_id}", headers=headers2)
    assert b_get_fail.status_code == 404

    # RBAC check: teacher cannot create building
    b_teacher_fail = await client.post(
        "/api/v1/buildings", json=b_payload, headers=t_headers
    )
    assert b_teacher_fail.status_code == 403

    # Teacher can read building list
    b_teacher_list = await client.get("/api/v1/buildings", headers=t_headers)
    assert b_teacher_list.status_code == 200
    assert len(b_teacher_list.json()["data"]) == 1

    # 2. Create Floor
    f_payload = {
        "building_id": b_id,
        "floor_number": 2,
        "floor_name": "Second Floor",
        "description": "Labs",
    }
    f_resp = await client.post("/api/v1/floors", json=f_payload, headers=headers1)
    assert f_resp.status_code == 201, f_resp.text
    f_id = f_resp.json()["data"]["id"]

    # Floor tenant check
    f_get_fail = await client.get(f"/api/v1/floors/{f_id}", headers=headers2)
    assert f_get_fail.status_code == 404

    # 3. Create Room
    r_payload = {
        "building_id": b_id,
        "floor_id": f_id,
        "room_code": "PHY-LAB",
        "room_name": "Physics Laboratory",
        "room_type": "LAB",
        "capacity": 30,
        "available_capacity": 30,
        "air_conditioned": True,
        "smart_classroom": True,
        "projector": True,
        "whiteboard": True,
        "computer_lab": False,
        "science_lab": True,
        "internet_enabled": True,
        "status": "active",
        "maintenance_status": "OPERATIONAL",
        "is_bookable": True,
        "is_active": True,
    }
    r_resp = await client.post("/api/v1/rooms", json=r_payload, headers=headers1)
    assert r_resp.status_code == 201, r_resp.text
    r_id = r_resp.json()["data"]["id"]

    # Room tenant isolation
    r_get_fail = await client.get(f"/api/v1/rooms/{r_id}", headers=headers2)
    assert r_get_fail.status_code == 404

    # 4. Check Room Availability & Summary
    avail_resp = await client.get(
        f"/api/v1/rooms/{r_id}/availability?occupants=25", headers=headers1
    )
    assert avail_resp.status_code == 200
    assert avail_resp.json()["data"] is True

    # Check excessive occupants
    avail_fail = await client.get(
        f"/api/v1/rooms/{r_id}/availability?occupants=35", headers=headers1
    )
    assert avail_fail.status_code == 200
    assert avail_fail.json()["data"] is False

    # Get Summary
    sum_resp = await client.get("/api/v1/rooms/summary", headers=headers1)
    assert sum_resp.status_code == 200
    assert sum_resp.json()["data"]["total_rooms"] == 1
    assert sum_resp.json()["data"]["lab_count"] == 1

    # 5. Manage Facilities
    fac_payload = {
        "room_id": r_id,
        "facility_name": "Spectrophotometer",
        "description": "High resolution chemistry/physics spectrometer",
        "quantity": 2,
    }
    fac_resp = await client.post(
        "/api/v1/facilities", json=fac_payload, headers=headers1
    )
    assert fac_resp.status_code == 201, fac_resp.text
    fac_id = fac_resp.json()["data"]["id"]

    # List facilities
    facs_list = await client.get(f"/api/v1/facilities?room_id={r_id}", headers=headers1)
    assert facs_list.status_code == 200
    assert len(facs_list.json()["data"]) == 1

    # Facility tenant check
    fac_get_fail = await client.get(f"/api/v1/facilities/{fac_id}", headers=headers2)
    assert fac_get_fail.status_code == 404

    # 6. Allocation Rules
    rule_payload = {
        "room_id": r_id,
        "allowed_class_levels": [str(uuid.uuid4())],
        "allowed_subjects": [str(uuid.uuid4())],
        "preferred_department_id": str(dept1.id),
        "maximum_occupancy": 30,
        "booking_priority": 3,
    }
    rule_resp = await client.post(
        "/api/v1/allocation-rules", json=rule_payload, headers=headers1
    )
    assert rule_resp.status_code == 201, rule_resp.text
    rule_id = rule_resp.json()["data"]["id"]

    # Delete rule first to allow trying to create another rule for the same room code
    del_rule_init = await client.delete(
        f"/api/v1/allocation-rules/{rule_id}", headers=headers1
    )
    assert del_rule_init.status_code == 200

    # Rule preferred department validation error check (department from school2)
    rule_invalid_dept_payload = {
        "room_id": r_id,
        "allowed_class_levels": [],
        "allowed_subjects": [],
        "preferred_department_id": str(dept2.id),  # Belongs to school2
        "maximum_occupancy": 30,
        "booking_priority": 1,
    }
    rule_fail_resp = await client.post(
        "/api/v1/allocation-rules", json=rule_invalid_dept_payload, headers=headers1
    )
    assert (
        rule_fail_resp.status_code == 404
    )  # Department not found exception since department is in school2 context

    # Recreate rule for subsequent tests
    rule_resp = await client.post(
        "/api/v1/allocation-rules", json=rule_payload, headers=headers1
    )
    assert rule_resp.status_code == 201
    rule_id = rule_resp.json()["data"]["id"]

    # Rule tenant isolation
    rule_get_fail = await client.get(
        f"/api/v1/allocation-rules/{rule_id}", headers=headers2
    )
    assert rule_get_fail.status_code == 404

    # 7. Update and Delete flow
    # Put Room under maintenance
    maint_resp = await client.put(
        f"/api/v1/rooms/{r_id}/maintenance?maintenance_status=UNDER_MAINTENANCE",
        headers=headers1,
    )
    assert maint_resp.status_code == 200
    assert maint_resp.json()["data"]["maintenance_status"] == "UNDER_MAINTENANCE"

    # Availability must now be False due to maintenance
    avail_maint = await client.get(
        f"/api/v1/rooms/{r_id}/availability?occupants=10", headers=headers1
    )
    assert avail_maint.json()["data"] is False

    # Delete everything
    del_rule = await client.delete(
        f"/api/v1/allocation-rules/{rule_id}", headers=headers1
    )
    assert del_rule.status_code == 200

    del_fac = await client.delete(f"/api/v1/facilities/{fac_id}", headers=headers1)
    assert del_fac.status_code == 200

    del_room = await client.delete(f"/api/v1/rooms/{r_id}", headers=headers1)
    assert del_room.status_code == 200

    del_floor = await client.delete(f"/api/v1/floors/{f_id}", headers=headers1)
    assert del_floor.status_code == 200

    del_bldg = await client.delete(f"/api/v1/buildings/{b_id}", headers=headers1)
    assert del_bldg.status_code == 200
