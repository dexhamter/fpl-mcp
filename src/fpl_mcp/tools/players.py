"""Player stats and history tools."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_player_stats",
        description=(
            "Return detailed season stats for a player: goals, assists, clean sheets, "
            "bonus points, ICT index, xG, xA, minutes played, and recent form."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "player_id": {
                    "type": "integer",
                    "description": "FPL element ID. Use search_player to find it.",
                },
                "player_name": {
                    "type": "string",
                    "description": "Search player by name instead of ID (partial, case-insensitive)",
                },
            },
        },
    ),
    types.Tool(
        name="get_player_history",
        description=(
            "Return a player's gameweek-by-gameweek performance history this season: "
            "points, minutes, goals, assists, bonus, price at each GW."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "player_id": {"type": "integer", "description": "FPL element ID"},
                "player_name": {"type": "string", "description": "Player name (partial match)"},
            },
        },
    ),
    types.Tool(
        name="get_top_performers",
        description=(
            "Return the top-performing players by total points, points-per-game, "
            "or form, optionally filtered by position or max price."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["total_points", "points_per_game", "form", "ict_index"],
                    "description": "Metric to rank by (default: total_points)",
                    "default": "total_points",
                },
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "max_price": {"type": "number", "description": "Maximum price in £M"},
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default: 20)",
                    "default": 20,
                },
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_player_stats":
        return await _get_player_stats(arguments, client)
    if name == "get_player_history":
        return await _get_player_history(arguments, client)
    if name == "get_top_performers":
        return await _get_top_performers(arguments, client)
    return None


async def _resolve_player_id(
    args: dict, client: FPLClient
) -> tuple[int, dict]:
    """Resolve player_id from args, searching by name if needed."""
    bootstrap = await client.get_bootstrap()
    elements = bootstrap["elements"]

    if pid := args.get("player_id"):
        el = next((e for e in elements if e["id"] == pid), None)
        if not el:
            raise ValueError(f"No player with ID {pid}")
        return pid, el

    if name := args.get("player_name"):
        query = name.lower()
        matches = [
            e for e in elements
            if query in e["web_name"].lower()
            or query in f"{e['first_name']} {e['second_name']}".lower()
        ]
        if not matches:
            raise ValueError(f"No player found matching '{name}'")
        return matches[0]["id"], matches[0]

    raise ValueError("Provide either player_id or player_name")


async def _get_player_stats(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    try:
        pid, el = await _resolve_player_id(args, client)
    except ValueError as e:
        return _text({"error": str(e)})

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}

    return _text({
        "id": el["id"],
        "name": f"{el['first_name']} {el['second_name']}",
        "web_name": el["web_name"],
        "team": teams.get(el["team"], "?"),
        "position": POSITION_MAP.get(el["element_type"], "?"),
        "price": el["now_cost"] / 10,
        "status": el["status"],
        "news": el["news"],
        "total_points": el["total_points"],
        "points_per_game": el["points_per_game"],
        "form": el["form"],
        "selected_by_percent": el["selected_by_percent"],
        "minutes": el["minutes"],
        "goals_scored": el["goals_scored"],
        "assists": el["assists"],
        "clean_sheets": el["clean_sheets"],
        "goals_conceded": el["goals_conceded"],
        "own_goals": el["own_goals"],
        "yellow_cards": el["yellow_cards"],
        "red_cards": el["red_cards"],
        "bonus": el["bonus"],
        "bps": el["bps"],
        "ict_index": el["ict_index"],
        "influence": el["influence"],
        "creativity": el["creativity"],
        "threat": el["threat"],
        "expected_goals": el.get("expected_goals"),
        "expected_assists": el.get("expected_assists"),
        "expected_goal_involvements": el.get("expected_goal_involvements"),
        "transfers_in_event": el["transfers_in_event"],
        "transfers_out_event": el["transfers_out_event"],
        "cost_change_event": el["cost_change_event"] / 10,
    })


async def _get_player_history(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    try:
        pid, el = await _resolve_player_id(args, client)
    except ValueError as e:
        return _text({"error": str(e)})

    summary = await client.get_element_summary(pid)
    history = [
        {
            "gameweek": h["round"],
            "opponent": h["opponent_team"],
            "home_away": "H" if h["was_home"] else "A",
            "minutes": h["minutes"],
            "points": h["total_points"],
            "goals": h["goals_scored"],
            "assists": h["assists"],
            "clean_sheet": h["clean_sheets"],
            "bonus": h["bonus"],
            "bps": h["bps"],
            "price": h["value"] / 10,
            "selected": h["selected"],
            "transfers_in": h["transfers_in"],
            "transfers_out": h["transfers_out"],
            "ict_index": h["ict_index"],
            "expected_goals": h.get("expected_goals"),
            "expected_assists": h.get("expected_assists"),
        }
        for h in summary.get("history", [])
    ]
    return _text({"player": el["web_name"], "history": history})


async def _get_top_performers(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    sort_by = args.get("sort_by", "total_points")
    position = args.get("position")
    max_price = args.get("max_price")
    limit = args.get("limit", 20)

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    if position:
        pos_id = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position)
        elements = [e for e in elements if e["element_type"] == pos_id]
    if max_price:
        elements = [e for e in elements if e["now_cost"] / 10 <= max_price]

    def sort_key(e):
        val = e.get(sort_by, 0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    elements = sorted(elements, key=sort_key, reverse=True)[:limit]

    result = [
        {
            "rank": i + 1,
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "total_points": e["total_points"],
            "points_per_game": e["points_per_game"],
            "form": e["form"],
            "ict_index": e["ict_index"],
            "selected_by_percent": e["selected_by_percent"],
            "status": e["status"],
        }
        for i, e in enumerate(elements)
    ]
    return _text({"sorted_by": sort_by, "players": result})


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
