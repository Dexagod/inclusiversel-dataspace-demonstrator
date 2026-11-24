# 0010: Request identity in call logs and read-only demo replay

The viewer needs to keep expanded calls open and distinguish interleaved clients.
Logs gain a unique `call_id` and an allowlisted `requester` object. MCP middleware
records request ID, reported client name/title/version when available, protocol,
session header, user-agent and peer address. Forwarded-for and demo client IDs are
reported metadata, not verified authentication. Authorization, cookies, arbitrary
headers and arbitrary MCP metadata are never recorded. Logging stays opt-in.

The connector stays stateless. It may lack initialized client information or a
session ID. The viewer groups by reported session ID, then declared client ID,
then an explicitly labelled address/client heuristic. Unknown old entries cannot
be reliably attributed. A per-client idle gap starts another group. Response
bodies remain absent from call logs.

`POST /demo/replay` accepts JSON `{tool, args}` for only the five existing read-only
tools. It calls `MCPServer.call_tool`, retaining SDK argument validation and source
OpenAPI/host/key checks. The reply is `{replayed_at, result}` with the SDK tool result.
Invalid bodies are rejected; the body is bounded at 64 KiB. There is no new
authentication model: the same five operations are already available through MCP.

The viewer exposes a matching same-origin `POST /api/logs/replay`, with a fixed
configured connector destination and no generic proxy. It identifies these calls
as viewer replays, never impersonates the original requester, and keeps results
only in the page's read-only text field. It rejects cross-origin browser requests.
Replays are fresh source reads and can differ from historical answers. They are
logged as new calls when logging is enabled. Stable DOM keys preserve expanded
groups/calls, scroll position, focus and replay results across polling updates.
