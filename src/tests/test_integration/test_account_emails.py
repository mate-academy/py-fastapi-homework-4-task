from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from database import ActivationTokenModel, PasswordResetTokenModel, UserModel


@pytest.mark.asyncio
async def test_account_notifications_include_saved_tokens(client, db_session, seed_user_groups, email_sender_stub):
    email = "notifications@mate.com"
    password = "StrongPassword123!"

    with (
        patch.object(email_sender_stub, "send_activation_email", new_callable=AsyncMock) as activation_email,
        patch.object(email_sender_stub, "send_activation_complete_email", new_callable=AsyncMock) as activation_done,
        patch.object(email_sender_stub, "send_password_reset_email", new_callable=AsyncMock) as reset_email,
        patch.object(email_sender_stub, "send_password_reset_complete_email", new_callable=AsyncMock) as reset_done,
    ):
        response = await client.post("/api/v1/accounts/register/", json={"email": email, "password": password})
        assert response.status_code == 201
        token = (await db_session.execute(select(ActivationTokenModel))).scalar_one()
        activation_email.assert_awaited_once()
        recipient, link = activation_email.await_args.args
        assert recipient == email
        assert urlparse(link).path == "/api/v1/accounts/activate/"
        assert parse_qs(urlparse(link).query) == {"email": [email], "token": [token.token]}

        response = await client.post("/api/v1/accounts/activate/", json={"email": email, "token": token.token})
        assert response.status_code == 200
        activation_done.assert_awaited_once()
        assert urlparse(activation_done.await_args.args[1]).path == "/api/v1/accounts/login/"

        response = await client.post("/api/v1/accounts/password-reset/request/", json={"email": email})
        assert response.status_code == 200
        user = (await db_session.execute(select(UserModel).where(UserModel.email == email))).scalar_one()
        token = (
            await db_session.execute(select(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id))
        ).scalar_one()
        reset_email.assert_awaited_once()
        recipient, link = reset_email.await_args.args
        assert recipient == email
        assert urlparse(link).path == "/api/v1/accounts/reset-password/complete/"
        assert parse_qs(urlparse(link).query) == {"email": [email], "token": [token.token]}

        response = await client.post(
            "/api/v1/accounts/reset-password/complete/",
            json={"email": email, "token": token.token, "password": "NewStrongPassword123!"},
        )
        assert response.status_code == 200
        reset_done.assert_awaited_once()
        assert urlparse(reset_done.await_args.args[1]).path == "/api/v1/accounts/login/"

        response = await client.post("/api/v1/accounts/password-reset/request/", json={"email": "missing@mate.com"})
        assert response.status_code == 200
        reset_email.assert_awaited_once()
