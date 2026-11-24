"""MCP tools for the Wizarr REST API.

Full API coverage, exposed as 7 resource-scoped *portmanteau* tools instead
of one tool per endpoint. Each tool takes an `operation` enum plus an
`arguments` dict; see AGENTS.md for the rationale (a 200+-tool server blows
the MCP context budget on session start). `_GROUPS` near the bottom buckets
every endpoint function by resource and `_register_group` wraps each bucket
in one dispatching MCP tool; the functions themselves are not tools anymore.

Wizarr's RESTX API lives at `/api/*` (not `/api/v1/*`) and authenticates with
an `X-API-Key` header. There is no connections endpoint in this API (Seerr was
registered as a companion through the web form) - server management is covered
by the read-only list endpoints. Request bodies stay plain JSON dictionaries
so this server follows the running version's DTOs without duplicating
validation.
"""

import inspect
import os
import sys
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

JSONObj = dict[str, Any]
JSONVal = JSONObj | list[Any]
ReturnVal = JSONVal | str | int | float | bool | None
READONLY = ToolAnnotations(readOnlyHint=True)

mcp = FastMCP("wizarr-mcp")
_client: httpx.AsyncClient | None = None


def build_client(
    base_url: str,
    api_key: str | None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.AsyncClient:
    headers = {"X-API-Key": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=f"{base_url.rstrip('/')}/api", headers=headers, transport=transport
    )


def _path(value: Any) -> str:
    return quote(str(value), safe="")


def _params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


async def _req(
    method: str,
    path: str,
    json: Any = None,
    params: dict[str, Any] | None = None,
) -> ReturnVal:
    assert _client is not None, "client not configured"
    response = await _client.request(method, path, json=json, params=params)
    if response.status_code >= 400:
        try:
            body = response.json()
            message = (
                body.get("error", body.get("message", body))
                if isinstance(body, dict)
                else body
            )
        except ValueError:
            message = response.text
        raise ToolError(f"Wizarr API {response.status_code}: {message}")
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return response.text


# system  ----------------------------------------------------------------------

async def wizarr_system_get_version() -> ReturnVal:
    """Get the installed Wizarr version (GET /api/version)."""
    return await _req("GET", "/version")


async def wizarr_system_get_status() -> ReturnVal:
    """Get overall statistics about your Wizarr instance: users, invites, pending, expired (GET /api/status)."""
    return await _req("GET", "/status")


# users  -----------------------------------------------------------------------

async def wizarr_user_list_users(username: str | None = None, email: str | None = None) -> ReturnVal:
    """List all users across all media servers. Supports filtering by username or email (exact match) (GET /api/users)."""
    return await _req("GET", "/users", params=_params(username=username, email=email))


async def wizarr_user_delete_user(user_id: int) -> ReturnVal:
    """Delete a specific user by ID (DELETE /api/users/{user_id})."""
    return await _req("DELETE", f"/users/{_path(user_id)}")


async def wizarr_user_disable_user(user_id: int) -> ReturnVal:
    """Disable a specific user by ID. Falls back to deleting the user when the server does not support disabling (POST /api/users/{user_id}/disable)."""
    return await _req("POST", f"/users/{_path(user_id)}/disable")


async def wizarr_user_enable_user(user_id: int) -> ReturnVal:
    """Enable a specific user by ID (POST /api/users/{user_id}/enable)."""
    return await _req("POST", f"/users/{_path(user_id)}/enable")


async def wizarr_user_extend_expiry(user_id: int, payload: dict) -> ReturnVal:
    """Extend a user's expiry date. Payload: {"days": <int>} (default 30) (POST /api/users/{user_id}/extend)."""
    return await _req("POST", f"/users/{_path(user_id)}/extend", json=payload)


async def wizarr_user_reset_password(user_id: int) -> ReturnVal:
    """Create a password reset token and link for a specific user (expires after 24 hours) (POST /api/users/{user_id}/reset-password)."""
    return await _req("POST", f"/users/{_path(user_id)}/reset-password")


async def wizarr_user_update_expiry(user_id: int, payload: dict) -> ReturnVal:
    """Update a user's expiry date to a specific date or unlimited. Payload: {"expires": "<ISO date-time>"}, null for unlimited (PUT /api/users/{user_id}/update-expiry)."""
    return await _req("PUT", f"/users/{_path(user_id)}/update-expiry", json=payload)


# invitations  -----------------------------------------------------------------

async def wizarr_invitation_list_invitations() -> ReturnVal:
    """List all invitations with their current status and server information (GET /api/invitations)."""
    return await _req("GET", "/invitations")


async def wizarr_invitation_create_invitation(payload: dict) -> ReturnVal:
    """Create a new invitation. Payload: {"server_ids": [<int>, ...], "expires_in_days": 1|7|30|null, "duration": "<days>|unlimited", "unlimited": <bool>, "library_ids": [<int>, ...], "allow_downloads": <bool>, "allow_live_tv": <bool>, "allow_mobile_uploads": <bool>, "wizard_bundle_id": <int>} (POST /api/invitations)."""
    return await _req("POST", "/invitations", json=payload)


async def wizarr_invitation_delete_invitation(invitation_id: int) -> ReturnVal:
    """Delete a specific invitation (DELETE /api/invitations/{invitation_id})."""
    return await _req("DELETE", f"/invitations/{_path(invitation_id)}")


# servers  ---------------------------------------------------------------------

async def wizarr_server_list_servers() -> ReturnVal:
    """List all configured media servers (GET /api/servers)."""
    return await _req("GET", "/servers")


async def wizarr_server_list_libraries() -> ReturnVal:
    """List all available libraries across all servers (GET /api/libraries)."""
    return await _req("GET", "/libraries")


# activity  --------------------------------------------------------------------

async def wizarr_activity_get_stats(days: str | None = None, start: str | None = None, end: str | None = None, server_id: str | None = None, username: str | None = None) -> ReturnVal:
    """Get the playback totals for a period, as on the Activity dashboard. days defaults to 30 (0 for all time); do not combine days with start/end (GET /api/activity/stats)."""
    return await _req("GET", "/activity/stats", params=_params(days=days, start=start, end=end, server_id=server_id, username=username))


async def wizarr_activity_list_users(days: str | None = None, start: str | None = None, end: str | None = None, server_id: str | None = None, username: str | None = None, limit: str | None = None) -> ReturnVal:
    """List the sessions and the watch time of each user in a period, most watch time first (GET /api/activity/users)."""
    return await _req("GET", "/activity/users", params=_params(days=days, start=start, end=end, server_id=server_id, username=username, limit=limit))


async def wizarr_activity_list_content(days: str | None = None, start: str | None = None, end: str | None = None, server_id: str | None = None, username: str | None = None, limit: str | None = None) -> ReturnVal:
    """List the plays and the watch time of each movie or series in a period, most plays first (GET /api/activity/content)."""
    return await _req("GET", "/activity/content", params=_params(days=days, start=start, end=end, server_id=server_id, username=username, limit=limit))


# admins  ----------------------------------------------------------------------

async def wizarr_admin_list_admins(username: str | None = None) -> ReturnVal:
    """List all Wizarr admins. Supports filtering by username (exact match) (GET /api/admins)."""
    return await _req("GET", "/admins", params=_params(username=username))


# api_keys  --------------------------------------------------------------------

async def wizarr_api_key_list_api_keys() -> ReturnVal:
    """List all active API keys (excluding the actual key values for security) (GET /api/api-keys)."""
    return await _req("GET", "/api-keys")


async def wizarr_api_key_delete_api_key(key_id: int) -> ReturnVal:
    """Delete a specific API key (soft delete - marks as inactive) (DELETE /api/api-keys/{key_id})."""
    return await _req("DELETE", f"/api-keys/{_path(key_id)}")


# Resource groups for portmanteau registration. Every tool function name
# must appear in exactly one group - see test_all_wizarr_grouped.
_GROUPS: dict[str, tuple[str, ...]] = {
    "wizarr_system": (
        "wizarr_system_get_status",
        "wizarr_system_get_version",
    ),
    "wizarr_users": (
        "wizarr_user_delete_user",
        "wizarr_user_disable_user",
        "wizarr_user_enable_user",
        "wizarr_user_extend_expiry",
        "wizarr_user_list_users",
        "wizarr_user_reset_password",
        "wizarr_user_update_expiry",
    ),
    "wizarr_invitations": (
        "wizarr_invitation_create_invitation",
        "wizarr_invitation_delete_invitation",
        "wizarr_invitation_list_invitations",
    ),
    "wizarr_servers": (
        "wizarr_server_list_libraries",
        "wizarr_server_list_servers",
    ),
    "wizarr_activity": (
        "wizarr_activity_get_stats",
        "wizarr_activity_list_content",
        "wizarr_activity_list_users",
    ),
    "wizarr_admins": (
        "wizarr_admin_list_admins",
    ),
    "wizarr_api_keys": (
        "wizarr_api_key_delete_api_key",
        "wizarr_api_key_list_api_keys",
    ),
}


def _op_line(name: str, fn: Any) -> str:
    """One line of a group tool's description: signature + one-line doc."""
    sig = ", ".join(
        p.name if p.default is inspect.Parameter.empty else f"{p.name}={p.default!r}"
        for p in inspect.signature(fn).parameters.values()
    )
    return f"- {name}({sig}) - {' '.join((fn.__doc__ or '').split())}"


def _register_group(
    group: str, names: tuple[str, ...], ns: dict[str, Any], readonly_names: set[str]
) -> None:
    """Register one dispatching tool that fans out to every function named
    in `names`. The functions themselves are untouched - they're just
    looked up by name instead of each becoming its own tool."""
    fns = {n: ns[n] for n in names}

    async def dispatch(
        operation: str, arguments: JSONObj | None = None
    ) -> ReturnVal:
        fn = fns.get(operation)
        if fn is None:
            raise ToolError(
                f"Unknown operation {operation!r} for {group}. Valid: {', '.join(fns)}"
            )
        return await fn(**(arguments or {}))

    dispatch.__annotations__["operation"] = Literal[names]
    ann = READONLY if set(names) <= readonly_names else None
    mcp.add_tool(
        Tool.from_function(
            dispatch,
            name=group,
            description=(
                f"{group.replace('_', ' ')} operations on Wizarr. Pass `operation` and an "
                f"`arguments` dict matching that operation's parameters.\n\n"
                + "\n".join(_op_line(n, f) for n, f in fns.items())
            ),
            annotations=ann,
        )
    )


def _register_tools() -> None:
    ns = globals()
    readonly_names: set[str] = {
        "wizarr_activity_get_stats",
        "wizarr_activity_list_content",
        "wizarr_activity_list_users",
        "wizarr_admin_list_admins",
        "wizarr_api_key_list_api_keys",
        "wizarr_invitation_list_invitations",
        "wizarr_server_list_libraries",
        "wizarr_server_list_servers",
        "wizarr_system_get_status",
        "wizarr_system_get_version",
        "wizarr_user_list_users",
    }
    for group, names in _GROUPS.items():
        _register_group(group, names, ns, readonly_names)


_register_tools()


def main() -> None:
    global _client
    url = os.environ.get("WIZARR_URL")
    if not url:
        print(
            "WIZARR_URL environment variable is required (e.g. http://10.10.10.18:5690)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _client = build_client(url, os.environ.get("WIZARR_API_KEY"))
    mcp.run()


if __name__ == "__main__":
    main()
