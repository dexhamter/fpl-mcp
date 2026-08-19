"""Bootstrap tools — players, teams, positions, prices, game settings."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_all_players",
        description=(
            "Return all FPL players with their current price, team, position, form, "
            "total points, selected_by_percent, and status. Optionally filter by position "
            "or team name."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "team": {
                    "type": "string",
                    "description": "Filter by team name (partial, case-insensitive, optional)",
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in £M (e.g. 6.5 means £6.5m)",
                },
                "min_form": {
                    "type": "number",
                    "description": "Minimum form value (optional)",
                },
            },
        },
    ),
    types.Tool(
        name="search_player",
        description="Search for a player by name (partial match, case-insensitive).",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Player name or partial name"},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_all_teams",
        description="Return all 20 Premier League teams with short name, strength ratings, and FPL team ID.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_game_settings",
        description=(
            "Return current gameweek info: current GW, next deadline, total players, "
            "average score, highest score, and the current top manager."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_all_players":
        return await _get_all_players(arguments, client)
    if name == "search_player":
        return await _search_player(arguments, client)
    if name == "get_all_teams":
        return await _get_all_teams(client)
    if name == "get_game_settings":
        return await _get_game_settings(client)
    return None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_all_players(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}
    players = _enrich_players(bootstrap["elements"], teams)

    # Filters
    if pos := args.get("position"):
        players = [p for p in players if p["position"] == pos]
    if team := args.get("team"):
        players = [p for p in players if team.lower() in p["team"].lower()]
    if max_price := args.get("max_price"):
        players = [p for p in players if p["price"] <= max_price]
    if min_form := args.get("min_form"):
        players = [p for p in players if float(p["form"]) >= min_form]

    players.sort(key=lambda p: p["total_points"], reverse=True)
    return _text(players)


async def _search_player(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    query = args["query"].lower()
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}
    players = _enrich_players(bootstrap["elements"], teams)
    results = [
        p
        for p in players
        if query in p["name"].lower() or query in p["web_name"].lower()
    ]
    return _text(results)


async def _get_all_teams(client: FPLClient) -> list[types.TextContent]:
    bootstrap = await client.get_bootstrap()
    teams = [
        {
            "id": t["id"],
            "name": t["name"],
            "short_name": t["short_name"],
            "strength": t["strength"],
            "strength_attack_home": t["strength_attack_home"],
            "strength_attack_away": t["strength_attack_away"],
            "strength_defence_home": t["strength_defence_home"],
            "strength_defence_away": t["strength_defence_away"],
        }
        for t in bootstrap["teams"]
    ]
    teams.sort(key=lambda t: t["name"])
    return _text(teams)


async def _get_game_settings(client: FPLClient) -> list[types.TextContent]:
    bootstrap = await client.get_bootstrap()
    events = bootstrap["events"]
    current = next((e for e in events if e.get("is_current")), None)
    nxt = next((e for e in events if e.get("is_next")), None)
    result = {
        "total_players": bootstrap["total_players"],
        "current_gameweek": current["id"] if current else None,
        "current_gw_deadline": current["deadline_time"] if current else None,
        "current_gw_average": current.get("average_entry_score") if current else None,
        "current_gw_highest": current.get("highest_score") if current else None,
        "next_gameweek": nxt["id"] if nxt else None,
        "next_gw_deadline": nxt["deadline_time"] if nxt else None,
        "season_name": events[0]["name"].replace(" 1", "") if events else None,
    }
    return _text(result)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _enrich_players(elements: list, teams: dict) -> list[dict]:
    return [
        {
            "id": e["id"],
            "name": f"{e['first_name']} {e['second_name']}",
            "web_name": e["web_name"],
            "team": teams.get(e["team"], "Unknown"),
            "team_id": e["team"],
            "position": POSITION_MAP.get(e["element_type"], "UNK"),
            "price": e["now_cost"] / 10,
            "form": e["form"],
            "total_points": e["total_points"],
            "points_per_game": e["points_per_game"],
            "selected_by_percent": e["selected_by_percent"],
            "status": e["status"],  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable
            "news": e["news"],
            "chance_of_playing_this_round": e["chance_of_playing_this_round"],
            "chance_of_playing_next_round": e["chance_of_playing_next_round"],
            "transfers_in_event": e["transfers_in_event"],
            "transfers_out_event": e["transfers_out_event"],
            "cost_change_event": e["cost_change_event"] / 10,  # price change this GW
            "cost_change_start": e["cost_change_start"] / 10,  # price change from season start
        }
        for e in elements
    ]


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
