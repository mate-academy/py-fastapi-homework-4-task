from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from database import UserModel


@pytest.mark.asyncio
async def test_two_logins_in_the_same_second_create_distinct_refresh_tokens(client, db_session, seed_user_groups):
    password = "StrongPassword123!"
    user = UserModel.create(email="login@mate.com", raw_password=password, group_id=1)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    with patch("security.token_manager.datetime") as clock:
        clock.now.return_value = datetime(2035, 1, 1, tzinfo=timezone.utc)
        first = await client.post("/api/v1/accounts/login/", json={"email": user.email, "password": password})
        second = await client.post("/api/v1/accounts/login/", json={"email": user.email, "password": password})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["refresh_token"] != second.json()["refresh_token"]
