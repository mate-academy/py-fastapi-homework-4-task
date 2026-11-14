from datetime import date, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import UserModel, UserProfileModel


@pytest.fixture
async def active_profile_user(db_session, seed_user_groups):
    user = UserModel.create(email="profile@mate.com", raw_password="StrongPassword123!", group_id=1)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def profile_form(image_format="JPEG", birth_date="1990-01-01"):
    image = BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(image, format=image_format)
    image.seek(0)
    return {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, birth_date),
        "info": (None, "A profile"),
        "avatar": ("avatar", image, "application/octet-stream"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_invalid_access_token_is_rejected_without_form_data(client, jwt_manager, expired):
    token = "invalid-token"
    if expired:
        token = jwt_manager.create_access_token({"user_id": 1}, expires_delta=timedelta(seconds=-1))
    response = await client.post(
        "/api/v1/profiles/users/1/profile/", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == ("Token has expired." if expired else "Invalid token.")


@pytest.mark.asyncio
async def test_profile_supports_png_content(client, active_profile_user, jwt_manager, s3_storage_fake):
    user = active_profile_user
    token = jwt_manager.create_access_token({"user_id": user.id})
    response = await client.post(
        f"/api/v1/profiles/users/{user.id}/profile/",
        headers={"Authorization": f"Bearer {token}"},
        files=profile_form("PNG"),
    )
    assert response.status_code == 201
    key = f"avatars/{user.id}_avatar.png"
    assert response.json()["avatar"].endswith(key)
    assert s3_storage_fake.storage[key].startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_profile_rejects_truncated_image(client, active_profile_user, jwt_manager, s3_storage_fake):
    user = active_profile_user
    token = jwt_manager.create_access_token({"user_id": user.id})
    form = profile_form("PNG")
    truncated_image = form["avatar"][1].getvalue()[:-12]
    form["avatar"] = ("avatar.png", BytesIO(truncated_image), "image/png")
    response = await client.post(
        f"/api/v1/profiles/users/{user.id}/profile/",
        headers={"Authorization": f"Bearer {token}"},
        files=form,
    )
    assert response.status_code == 422
    assert not s3_storage_fake.storage


@pytest.mark.asyncio
async def test_profile_requires_actual_eighteenth_birthday(client, active_profile_user, jwt_manager):
    user = active_profile_user
    token = jwt_manager.create_access_token({"user_id": user.id})
    today = date.today()
    if today.month == 2 and today.day == 29:
        birth_date = date(today.year - 18, 3, 1)
    else:
        birth_date = today.replace(year=today.year - 18) + timedelta(days=1)
    response = await client.post(
        f"/api/v1/profiles/users/{user.id}/profile/",
        headers={"Authorization": f"Bearer {token}"},
        files=profile_form(birth_date=birth_date.isoformat()),
    )
    assert response.status_code == 422
    assert "You must be at least 18 years old to register." in str(response.json())


@pytest.mark.asyncio
async def test_failed_profile_commit_removes_uploaded_avatar(
        client, db_session, active_profile_user, jwt_manager, s3_storage_fake
):
    user = active_profile_user
    token = jwt_manager.create_access_token({"user_id": user.id})
    with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock) as commit:
        commit.side_effect = SQLAlchemyError("Commit failed")
        response = await client.post(
            f"/api/v1/profiles/users/{user.id}/profile/",
            headers={"Authorization": f"Bearer {token}"},
            files=profile_form(),
        )
    assert response.status_code == 500
    assert not s3_storage_fake.storage
    result = await db_session.execute(select(UserProfileModel).where(UserProfileModel.user_id == user.id))
    assert result.scalar_one_or_none() is None
