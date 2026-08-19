"""League standings tools."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient

TOOLS = [
    types.Tool(
        name="get_my_leagues",
        description="Return all mini-leagues your team belongs to (classic and H2H).",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_classic_league_standings",
        description="Return the standings table for a classic league.",
        inputSchema={
            "type": "object",
            "properties": {
                "league_id": {"type": "integer", "description": "Classic league ID"},
                "page": {
                    "type": "integer",
                    "description": "Page of standings (50 per page, default: 1)",
                    "default": 1,
                },
            },
            "required": ["league_id"],
        },
    ),
    types.Tool(
        name="get_h2h_league_standings",
        description="Return the standings table for a Head-to-Head league.",
        inputSchema={
            "type": "object",
            "properties": {
                "league_id": {"type": "integer", "description": "H2H league ID"},
                "page": {
                    "type": "integer",
                    "description": "Page of standings (default: 1)",
                    "default": 1,
                },
            },
            "required": ["league_id"],
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_my_leagues":
        return await _get_my_leagues(client)
    if name == "get_classic_league_standings":
        return await _get_classic_league_standings(arguments, client)
    if name == "get_h2h_league_standings":
        return await _get_h2h_league_standings(arguments, client)
    return None


async def _get_my_leagues(client: FPLClient) -> list[types.TextContent]:
    entry = await client.get_entry()
    leagues = entry.get("leagues", {})
    return _text({
        "classic_leagues": [
            {
                "id": l["id"],
                "name": l["name"],
                "my_rank": l["entry_rank"],
                "last_rank": l["entry_last_rank"],
                "rank_change": l["entry_last_rank"] - l["entry_rank"],
                "admin_entry": l.get("admin_entry"),
            }
            for l in leagues.get("classic", [])
        ],
        "h2h_leagues": [
            {
                "id": l["id"],
                "name": l["name"],
                "admin_entry": l.get("admin_entry"),
            }
            for l in leagues.get("h2h", [])
        ],
    })


async def _get_classic_league_standings(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    league_id = args["league_id"]
    page = args.get("page", 1)
    data = await client.get_classic_league(league_id=league_id, page=page)
    league = data.get("league", {})
    standings = data.get("standings", {})
    return _text({
        "league_id": league_id,
        "league_name": league.get("name"),
        "page": page,
        "has_next": standings.get("has_next", False),
        "standings": [
            {
                "rank": r["rank"],
                "last_rank": r["last_rank"],
                "team_id": r["entry"],
                "team_name": r["entry_name"],
                "manager": r["player_name"],
                "total": r["total"],
                "gw_points": r["event_total"],
            }
            for r in standings.get("results", [])
        ],
    })


async def _get_h2h_league_standings(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    league_id = args["league_id"]
    page = args.get("page", 1)
    data = await client.get_h2h_league(league_id=league_id, page=page)
    league = data.get("league", {})
    standings = data.get("standings", {})
    return _text({
        "league_id": league_id,
        "league_name": league.get("name"),
        "page": page,
        "has_next": standings.get("has_next", False),
        "standings": [
            {
                "rank": r["rank"],
                "team_id": r["entry"],
                "team_name": r["entry_name"],
                "manager": r["player_name"],
                "matches_won": r["matches_won"],
                "matches_drawn": r["matches_drawn"],
                "matches_lost": r["matches_lost"],
                "points_for": r["points_for"],
                "total": r["total"],
            }
            for r in standings.get("results", [])
        ],
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
