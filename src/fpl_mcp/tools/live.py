"""Live gameweek scores tools."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_live_gw_scores",
        description=(
            "Return live points for all players in the current (or specified) gameweek. "
            "Shows goals, assists, bonus, minutes, and provisional points."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "gameweek": {
                    "type": "integer",
                    "description": "Gameweek number (defaults to current GW)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["points", "bonus", "goals", "assists"],
                    "description": "Sort field (default: points)",
                    "default": "points",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of top players to return (default: 30)",
                    "default": 30,
                },
            },
        },
    ),
    types.Tool(
        name="get_my_live_score",
        description=(
            "Return my current squad's live score for this gameweek: "
            "each player's provisional points, auto-subs applied, and running total."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "gameweek": {
                    "type": "integer",
                    "description": "Gameweek number (defaults to current GW)",
                }
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_live_gw_scores":
        return await _get_live_gw_scores(arguments, client)
    if name == "get_my_live_score":
        return await _get_my_live_score(arguments, client)
    return None


async def _current_gw(client: FPLClient) -> int:
    bootstrap = await client.get_bootstrap()
    events = bootstrap["events"]
    current = next((e["id"] for e in events if e.get("is_current")), None)
    return current or max(e["id"] for e in events)


async def _get_live_gw_scores(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    gw = args.get("gameweek") or await _current_gw(client)
    sort_by = args.get("sort_by", "points")
    limit = args.get("limit", 30)

    live = await client.get_event_live(gw)
    bootstrap = await client.get_bootstrap()
    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    rows = []
    for el_id_str, el_data in live.get("elements", {}).items():
        el_id = int(el_id_str)
        stats = el_data.get("stats", {})
        player = players_by_id.get(el_id, {})
        rows.append({
            "id": el_id,
            "name": player.get("web_name", str(el_id)),
            "team": teams.get(player.get("team"), "?"),
            "position": POSITION_MAP.get(player.get("element_type"), "?"),
            "minutes": stats.get("minutes", 0),
            "points": stats.get("total_points", 0),
            "goals": stats.get("goals_scored", 0),
            "assists": stats.get("assists", 0),
            "clean_sheets": stats.get("clean_sheets", 0),
            "bonus": stats.get("bonus", 0),
            "bps": stats.get("bps", 0),
            "yellow_cards": stats.get("yellow_cards", 0),
            "red_cards": stats.get("red_cards", 0),
            "own_goals": stats.get("own_goals", 0),
            "in_dreamteam": el_data.get("in_dreamteam", False),
        })

    sort_map = {"points": "points", "bonus": "bonus", "goals": "goals", "assists": "assists"}
    rows.sort(key=lambda r: r[sort_map.get(sort_by, "points")], reverse=True)
    rows = rows[:limit]

    return _text({"gameweek": gw, "sorted_by": sort_by, "players": rows})


async def _get_my_live_score(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    gw = args.get("gameweek") or await _current_gw(client)

    picks_data = await client.get_entry_picks(gw=gw)
    live = await client.get_event_live(gw)
    bootstrap = await client.get_bootstrap()
    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    live_elements = live.get("elements", {})
    picks = picks_data.get("picks", [])
    active_chip = picks_data.get("active_chip")
    entry_history = picks_data.get("entry_history", {})

    player_scores = []
    total = 0
    for pick in picks:
        el_id = pick["element"]
        stats = live_elements.get(str(el_id), {}).get("stats", {})
        multiplier = pick.get("multiplier", 1)
        pts = stats.get("total_points", 0) * multiplier
        if multiplier > 0:  # not benched (bench players have multiplier 0 in some contexts)
            total += pts
        player = players_by_id.get(el_id, {})
        player_scores.append({
            "element_id": el_id,
            "name": player.get("web_name", str(el_id)),
            "team": teams.get(player.get("team"), "?"),
            "position": POSITION_MAP.get(player.get("element_type"), "?"),
            "starting": pick.get("position", 15) <= 11,
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            "multiplier": multiplier,
            "minutes": stats.get("minutes", 0),
            "raw_points": stats.get("total_points", 0),
            "total_points_with_multiplier": pts,
            "goals": stats.get("goals_scored", 0),
            "assists": stats.get("assists", 0),
            "bonus": stats.get("bonus", 0),
            "yellow_cards": stats.get("yellow_cards", 0),
            "red_cards": stats.get("red_cards", 0),
        })

    transfer_cost = entry_history.get("event_transfers_cost", 0)
    return _text({
        "gameweek": gw,
        "active_chip": active_chip,
        "live_total": total,
        "transfer_cost": transfer_cost,
        "net_total": total - transfer_cost,
        "players": player_scores,
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
