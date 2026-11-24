"""Opt-in smoke tests for a live Wizarr instance (read-only)."""

import os

import pytest
from fastmcp import Client

import wizarr_mcp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("WIZARR_URL"),
        reason="requires WIZARR_URL (and WIZARR_API_KEY)",
    ),
]


@pytest.fixture(autouse=True)
def configure_client():
    wizarr_mcp._client = wizarr_mcp.build_client(
        os.environ["WIZARR_URL"], os.environ.get("WIZARR_API_KEY")
    )
    yield


async def call(group, operation, **arguments):
    async with Client(wizarr_mcp.mcp) as client:
        return await client.call_tool(
            group, {"operation": operation, "arguments": arguments}
        )


async def test_version_and_status():
    version = await call("wizarr_system", "wizarr_system_get_version")
    assert version.data is not None
    status = await call("wizarr_system", "wizarr_system_get_status")
    assert status.data is not None


async def test_users_and_servers():
    assert (
        await call("wizarr_users", "wizarr_user_list_users")
    ).data is not None
    assert (
        await call("wizarr_servers", "wizarr_server_list_servers")
    ).data is not None
    assert (
        await call("wizarr_servers", "wizarr_server_list_libraries")
    ).data is not None


async def test_invitations_admins_and_activity():
    assert (
        await call("wizarr_invitations", "wizarr_invitation_list_invitations")
    ).data is not None
    assert (
        await call("wizarr_admins", "wizarr_admin_list_admins")
    ).data is not None
    assert (
        await call("wizarr_activity", "wizarr_activity_get_stats")
    ).data is not None
