"""Offline contract tests for the Wizarr MCP tools."""

import inspect
import json

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

import wizarr_mcp


class Recorder:
    def __init__(self):
        self.method = None
        self.url = None
        self.headers = None
        self.json = None
        self.raw = None
        self.response = httpx.Response(200, json={"ok": True})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.method = request.method
        self.url = request.url
        self.headers = request.headers
        self.raw = request.content
        try:
            self.json = json.loads(request.content) if request.content else None
        except ValueError:
            self.json = None
        return self.response


@pytest.fixture
def recorder():
    return Recorder()


@pytest_asyncio.fixture
async def server(recorder, monkeypatch):
    client = wizarr_mcp.build_client(
        "http://10.10.10.18:5690",
        "test-key",
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(wizarr_mcp, "_client", client)
    yield wizarr_mcp.mcp
    await client.aclose()


_OP_GROUP = {
    op: group for group, ops in wizarr_mcp._GROUPS.items() for op in ops
}


async def call(server, op_name, **kwargs):
    """Call `op_name` (an operation name) through its portmanteau tool."""
    async with Client(server) as client:
        return await client.call_tool(
            _OP_GROUP[op_name], {"operation": op_name, "arguments": kwargs}
        )


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path"),
    [
        ("wizarr_system_get_version", {}, "GET", "/api/version"),
        ("wizarr_system_get_status", {}, "GET", "/api/status"),
        ("wizarr_user_list_users", {}, "GET", "/api/users"),
        ("wizarr_user_delete_user", {"user_id": 3}, "DELETE", "/api/users/3"),
        ("wizarr_user_disable_user", {"user_id": 3}, "POST", "/api/users/3/disable"),
        ("wizarr_user_enable_user", {"user_id": 3}, "POST", "/api/users/3/enable"),
        (
            "wizarr_user_reset_password",
            {"user_id": 3},
            "POST",
            "/api/users/3/reset-password",
        ),
        (
            "wizarr_user_update_expiry",
            {"user_id": 3, "payload": {}},
            "PUT",
            "/api/users/3/update-expiry",
        ),
        ("wizarr_invitation_list_invitations", {}, "GET", "/api/invitations"),
        (
            "wizarr_invitation_create_invitation",
            {"payload": {}},
            "POST",
            "/api/invitations",
        ),
        (
            "wizarr_invitation_delete_invitation",
            {"invitation_id": 5},
            "DELETE",
            "/api/invitations/5",
        ),
        ("wizarr_server_list_servers", {}, "GET", "/api/servers"),
        ("wizarr_server_list_libraries", {}, "GET", "/api/libraries"),
        ("wizarr_activity_get_stats", {}, "GET", "/api/activity/stats"),
        ("wizarr_activity_list_users", {}, "GET", "/api/activity/users"),
        ("wizarr_activity_list_content", {}, "GET", "/api/activity/content"),
        ("wizarr_admin_list_admins", {}, "GET", "/api/admins"),
        ("wizarr_api_key_list_api_keys", {}, "GET", "/api/api-keys"),
        ("wizarr_api_key_delete_api_key", {"key_id": 2}, "DELETE", "/api/api-keys/2"),
    ],
)
async def test_endpoint_routes(server, recorder, name, kwargs, method, path):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.raw_path.split(b"?")[0].decode() == path


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path", "body"),
    [
        (
            "wizarr_user_extend_expiry",
            {"user_id": 3, "payload": {"days": 30}},
            "POST",
            "/api/users/3/extend",
            {"days": 30},
        ),
        (
            "wizarr_user_update_expiry",
            {"user_id": 3, "payload": {"expires": None}},
            "PUT",
            "/api/users/3/update-expiry",
            {"expires": None},
        ),
        (
            "wizarr_invitation_create_invitation",
            {"payload": {"server_ids": [1], "duration": "unlimited"}},
            "POST",
            "/api/invitations",
            {"server_ids": [1], "duration": "unlimited"},
        ),
    ],
)
async def test_request_bodies(server, recorder, name, kwargs, method, path, body):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.path == path
    assert recorder.json == body


async def test_query_parameters(server, recorder):
    await call(
        server,
        "wizarr_user_list_users",
        username="savagecore",
        email="talk@savagecore.uk",
    )
    assert recorder.url.params["username"] == "savagecore"
    assert recorder.url.params["email"] == "talk@savagecore.uk"


async def test_activity_query_parameters(server, recorder):
    await call(
        server,
        "wizarr_activity_list_content",
        days="7",
        server_id="1",
        username="savagecore",
        limit="10",
    )
    assert recorder.url.params["days"] == "7"
    assert recorder.url.params["server_id"] == "1"
    assert recorder.url.params["username"] == "savagecore"
    assert recorder.url.params["limit"] == "10"


async def test_api_key_header(server, recorder):
    await call(server, "wizarr_system_get_status")
    assert recorder.headers["x-api-key"] == "test-key"


async def test_no_api_key_header(recorder, monkeypatch):
    client = wizarr_mcp.build_client(
        "http://10.10.10.18:5690",
        None,
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(wizarr_mcp, "_client", client)
    await call(wizarr_mcp.mcp, "wizarr_system_get_status")
    assert "x-api-key" not in recorder.headers
    await client.aclose()


async def test_error_message(server, recorder):
    recorder.response = httpx.Response(404, json={"error": "User not found"})
    with pytest.raises(ToolError, match="404.*User not found"):
        await call(server, "wizarr_user_delete_user", user_id=999)


async def test_non_json_error(server, recorder):
    recorder.response = httpx.Response(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ToolError, match="502"):
        await call(server, "wizarr_system_get_status")


def test_main_requires_url(monkeypatch):
    monkeypatch.delenv("WIZARR_URL", raising=False)
    with pytest.raises(SystemExit):
        wizarr_mcp.main()


# --- full-surface smoke coverage ---------------------------------------------
# Only a subset of the 20 operations has exact request-shape assertions above.
# This exercises every endpoint function's URL-templating/body-marshaling path
# with type-appropriate dummy arguments, so all grouped operations are covered.

ALL_ENDPOINT_NAMES = sorted(
    name
    for name in dir(wizarr_mcp)
    if name.startswith("wizarr_")
    and inspect.iscoroutinefunction(getattr(wizarr_mcp, name))
)


def _sample_value(param: inspect.Parameter):
    ann = str(param.annotation)
    if "dict" in ann:
        return {}
    if "list" in ann:
        return []
    if "bool" in ann:
        return True
    if "int" in ann:
        return 1
    if "float" in ann:
        return 1
    return "x"


@pytest.mark.parametrize("name", ALL_ENDPOINT_NAMES)
async def test_every_endpoint_is_callable(server, recorder, name):
    fn = getattr(wizarr_mcp, name)
    kwargs = {
        p.name: _sample_value(p)
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
    }
    await call(server, name, **kwargs)
    assert recorder.method in ("GET", "POST", "PUT", "DELETE", "PATCH")
    assert recorder.url.path.startswith("/")


# --- portmanteau grouping safety net ------------------------------------------

def test_all_wizarr_grouped():
    """Every endpoint function must land in exactly one portmanteau group."""
    grouped_names = [n for names in wizarr_mcp._GROUPS.values() for n in names]
    assert sorted(grouped_names) == sorted(ALL_ENDPOINT_NAMES)
    assert len(grouped_names) == len(set(grouped_names))


async def test_group_tools_are_the_only_registered_tools(server):
    async with Client(server) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == set(wizarr_mcp._GROUPS)


async def test_unknown_operation_rejected_by_schema(server):
    # The Literal[...] enum on `operation` means an invalid value never reaches
    # _register_group's dispatch body - pydantic rejects it first.
    with pytest.raises(ToolError, match="validation error"):
        async with Client(server) as client:
            await client.call_tool("wizarr_users", {"operation": "not_real"})
