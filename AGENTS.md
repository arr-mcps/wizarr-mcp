# AGENTS.md - wizarr-mcp

MCP server exposing Wizarr's REST API as 7 resource-scoped portmanteau
tools (20 operations). Uses FastMCP, `uv` for deps. Tested against Wizarr
2026.10.1 (the version running in CT 114 on the new box).

## Tool design

Exactly 7 tools are registered, one per entry in `_GROUPS` in
`wizarr_mcp.py`: `wizarr_system`, `wizarr_users`, `wizarr_invitations`,
`wizarr_servers`, `wizarr_activity`, `wizarr_admins`, `wizarr_api_keys`.
Each tool takes an `operation` (a `Literal` of its functions' names) plus an
`arguments` dict and dispatches to a plain async endpoint function. Do not
register individual endpoint functions as tools. See the arr-mcps masterlist
`AGENTS.md` for the rationale (a 200+-tool server blows the MCP context budget).

`_register_group` marks a group `readOnlyHint=True` only when every operation
in it is a GET. Currently `wizarr_system`, `wizarr_servers`,
`wizarr_activity` and `wizarr_admins` are read-only; `wizarr_users`,
`wizarr_invitations` and `wizarr_api_keys` are mixed.

The endpoint list and canonical paths came from the live RESTX spec at
`http://10.10.10.18:5690/api/swagger.json` (Wizarr API 2.2.1 surface), verified
against the running instance. If Wizarr is upgraded, re-check that spec before
adding endpoints. Error bodies use an `error` key (not `message`), which
`_req` surfaces; both shapes are handled.

There is no connections endpoint in this API (Seerr was registered as a
companion through the web form, not the API), so server management here is
read-only listing. The optional `X-Fields` response mask header is not
exposed - tools return full objects.

`return` types of endpoint helpers are plain JSON pass-through dictionaries.
Do not place real API keys, passwords, or tokens in tool descriptions
or commit messages.

## Testing

- Offline suite: `make test` (or `uv run pytest`)
- Live integration, read-only (needs `WIZARR_URL` + `WIZARR_API_KEY`): `make test-integration`
- `tests/test_tools.py` has exact request-shape assertions for a subset, a
  generic smoke test that executes every endpoint function through its group
  with type-appropriate dummy arguments, and `test_all_wizarr_grouped`,
  which asserts every endpoint function appears in exactly one `_GROUPS` entry.
- Never create invitations/users or modify anything on the live service from
  tests - integration tests are GET-only.

## Release workflow

Use `make bump-*` (`uv version --bump patch|minor|major`), which updates
`pyproject.toml` and `uv.lock` together. Never hand-edit the version. Commit
message is just the version, tag `v<version>`, then push main and the tag.
This server is version `0.0.0` (unreleased, like maintainerr-mcp was at
scaffolding); no GitHub repo or tag has been created.
