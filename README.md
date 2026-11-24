# wizarr-mcp

Part of the [arr-mcps](https://github.com/arr-mcps/arr-mcps) collection.
An MCP server exposing [Wizarr](https://github.com/wizarrrr/wizarr)'s
REST API as tools for managing users, invitations, servers, libraries,
activity stats, admins, and API keys.

## Requirements

- Wizarr with its REST API reachable (tested against 2026.10.1)
- Python 3.11+ and `uv` for source development

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `WIZARR_URL` | Yes | Wizarr base URL, for example `http://10.10.10.18:5690`. The server appends `/api`. |
| `WIZARR_API_KEY` | Yes | API key sent as `X-API-Key`. Wizarr requires it on every endpoint. |

Install a built wheel and register it with Claude Code:

```bash
uv tool install wizarr_mcp-*.whl
claude mcp add wizarr \
  --env WIZARR_URL=http://10.10.10.18:5690 \
  --env WIZARR_API_KEY=... \
  -- wizarr-mcp
```

For a source checkout:

```bash
uv sync
claude mcp add wizarr \
  --env WIZARR_URL=http://10.10.10.18:5690 \
  --env WIZARR_API_KEY=... \
  -- uv run --directory /path/to/wizarr-mcp wizarr-mcp
```

## Tools

**7 resource-scoped tools** cover all 20 Wizarr REST operations via an
`operation` parameter. Call a tool with `operation` set to one of its listed
operations and an `arguments` dict matching that operation's parameters. Each
tool's own description (visible to your MCP client) lists every operation, its
signature, and a one-line doc, so no discovery round-trip is needed. This keeps
the whole API available while costing a fraction of the context budget of
registering 20 endpoints as separate tools.

| Tool | Operations | Covers |
| --- | --- | --- |
| `wizarr_users` | 7 | List, delete, disable, enable, extend expiry, reset password, update expiry |
| `wizarr_invitations` | 3 | List, create, delete invitations |
| `wizarr_activity` | 3 | Playback stats, per-user and per-title watch time |
| `wizarr_system` | 2 | Version, instance status (user/invite counts) |
| `wizarr_servers` | 2 | Media servers, libraries across all servers |
| `wizarr_api_keys` | 2 | List and delete (soft) API keys |
| `wizarr_admins` | 1 | List Wizarr admins |

Endpoint-level naming (`wizarr_<resource>_<verb>_<target>`) is kept as
the `operation` value, so the full endpoint list is discoverable from each
group tool's description at runtime. The `system`, `servers`, `activity` and
`admins` groups are marked `readOnlyHint=True`; the other three groups contain
write operations and carry no hint.

Example:

```text
wizarr_system(operation="wizarr_system_get_status", arguments={})
wizarr_users(operation="wizarr_user_list_users", arguments={"username": "savagecore"})
wizarr_activity(operation="wizarr_activity_get_stats", arguments={"days": "7"})
```

Notes on special operations:

- Body payloads are pass-through JSON dictionaries matching the DTOs of the
  running Wizarr version. Do not put real API keys, passwords, or tokens in
  prompts.
- There is no connections endpoint in Wizarr's RESTX API (companions such as
  Seerr are registered through the web form), so server management here is
  read-only listing.

## Development

```bash
make sync
make test
make test-integration   # requires WIZARR_URL and WIZARR_API_KEY (read-only)
make build
```

The offline tests use `httpx.MockTransport`; integration tests are skipped by
default.
