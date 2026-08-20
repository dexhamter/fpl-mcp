"""Team news tools — injuries, suspensions, set piece takers."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_player_news",
        description=(
            "Return all players with injury/suspension news, sorted by ownership. "
            "Shows status, news text, and chance of playing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["doubtful", "injured", "suspended", "unavailable", "all"],
                    "description": "Filter by availability status (default: all non-available)",
                    "default": "all",
                }
            },
        },
    ),
    types.Tool(
        name="get_set_piece_takers",
        description=(
            "Return penalty, corner, and free-kick takers for each Premier League team. "
            "Data sourced from FPL element notes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Filter to a specific team (partial, optional)",
                }
            },
        },
    ),
    types.Tool(
        name="check_my_squad_news",
        description=(
            "Check all 15 players in your current squad for injury/suspension news. "
            "Highlights players with availability concerns."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
]

STATUS_CODES = {
    "a": "Available",
    "d": "Doubtful",
    "i": "Injured",
    "s": "Suspended",
    "u": "Unavailable",
    "n": "Not in squad",
}


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_player_news":
        return await _get_player_news(arguments, client)
    if name == "get_set_piece_takers":
        return await _get_set_piece_takers(arguments, client)
    if name == "check_my_squad_news":
        return await _check_my_squad_news(client)
    return None


async def _get_player_news(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    status_filter = args.get("status", "all")
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    status_map = {
        "doubtful": ["d"],
        "injured": ["i"],
        "suspended": ["s"],
        "unavailable": ["u"],
        "all": ["d", "i", "s", "u"],
    }
    codes = status_map.get(status_filter, ["d", "i", "s", "u"])

    players = [
        {
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "status": STATUS_CODES.get(e["status"], e["status"]),
            "news": e["news"],
            "news_added": e.get("news_added"),
            "chance_this_round": e["chance_of_playing_this_round"],
            "chance_next_round": e["chance_of_playing_next_round"],
            "selected_by_percent": e["selected_by_percent"],
        }
        for e in bootstrap["elements"]
        if e["status"] in codes and e["news"]
    ]

    players.sort(
        key=lambda p: float(p["selected_by_percent"] or 0), reverse=True
    )
    return _text({"count": len(players), "players_with_news": players})


async def _get_set_piece_takers(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    team_filter = args.get("team_name", "").lower()
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    # Group players by team
    by_team: dict[int, list] = {}
    for e in elements:
        by_team.setdefault(e["team"], []).append(e)

    result = []
    for team_id, team in teams.items():
        if team_filter and team_filter not in team["name"].lower() and team_filter not in team["short_name"].lower():
            continue

        team_players = by_team.get(team_id, [])

        # Penalty takers: sort by penalties_order if available, else by threat
        penalties = sorted(
            [e for e in team_players if e.get("penalties_order") is not None],
            key=lambda e: e["penalties_order"],
        )
        direct_freekicks = sorted(
            [e for e in team_players if e.get("direct_freekicks_order") is not None],
            key=lambda e: e["direct_freekicks_order"],
        )
        corners = sorted(
            [e for e in team_players if e.get("corners_and_indirect_freekicks_order") is not None],
            key=lambda e: e["corners_and_indirect_freekicks_order"],
        )

        result.append({
            "team": team["name"],
            "short": team["short_name"],
            "penalty_takers": [{"name": e["web_name"], "order": e["penalties_order"]} for e in penalties[:3]],
            "direct_freekick_takers": [{"name": e["web_name"], "order": e["direct_freekicks_order"]} for e in direct_freekicks[:3]],
            "corner_takers": [{"name": e["web_name"], "order": e["corners_and_indirect_freekicks_order"]} for e in corners[:3]],
        })

    result.sort(key=lambda r: r["team"])
    return _text(result)


async def _check_my_squad_news(client: FPLClient) -> list[types.TextContent]:
    my_ids = set()
    try:
        my_team = await client.get_my_team()
        picks = my_team.get("picks", [])
        my_ids = {p["element"] for p in picks}
    except Exception:
        bootstrap = await client.get_bootstrap()
        events = bootstrap["events"]
        current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
        try:
            entry_picks = await client.get_entry_picks(gw=current_gw)
            my_ids = {p["element"] for p in entry_picks.get("picks", [])}
        except Exception:
            from pathlib import Path
            state_dir = Path("agent/state")
            squad_files = sorted(state_dir.glob("squad-gw*.json"), reverse=True) if state_dir.exists() else []
            if squad_files:
                try:
                    squad_data = json.loads(squad_files[0].read_text(encoding="utf-8"))
                    my_ids = {p["id"] for p in squad_data.get("squad", [])}
                except Exception:
                    my_ids = set()

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    concerns = []
    all_clear = []
    for e in bootstrap["elements"]:
        if e["id"] not in my_ids:
            continue
        entry = {
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "status": STATUS_CODES.get(e["status"], e["status"]),
            "news": e["news"],
            "chance_this_round": e["chance_of_playing_this_round"],
        }
        if e["status"] != "a" or e["news"]:
            concerns.append(entry)
        else:
            all_clear.append(entry)

    return _text({
        "squad_size": len(my_ids),
        "players_with_concerns": len(concerns),
        "concerns": concerns,
        "all_clear": [p["name"] for p in all_clear],
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
