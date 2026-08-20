"""Squad tools — my team, captain, picks, entry info."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import CHIP_NAMES, POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_my_squad",
        description=(
            "Return your current FPL squad: all 15 players with their position, price, "
            "playing status, and which is captain/vice-captain/benched."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_entry_info",
        description=(
            "Return your team's overview: team name, overall rank, total points, "
            "team value, bank balance, and gameweek history summary."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "FPL team ID (defaults to your team if omitted)",
                }
            },
        },
    ),
    types.Tool(
        name="get_gw_picks",
        description=(
            "Return the squad picks for a specific gameweek: starting XI, bench, "
            "captain, vice-captain, active chip, and points scored."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "gameweek": {
                    "type": "integer",
                    "description": "Gameweek number (1-38)",
                },
                "team_id": {
                    "type": "integer",
                    "description": "FPL team ID (defaults to your team if omitted)",
                },
            },
            "required": ["gameweek"],
        },
    ),
    types.Tool(
        name="get_season_history",
        description="Return your points and rank for each completed gameweek this season.",
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "FPL team ID (defaults to your team if omitted)",
                }
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_my_squad":
        return await _get_my_squad(client)
    if name == "get_entry_info":
        return await _get_entry_info(arguments, client)
    if name == "get_gw_picks":
        return await _get_gw_picks(arguments, client)
    if name == "get_season_history":
        return await _get_season_history(arguments, client)
    return None


async def _get_my_squad(client: FPLClient) -> list[types.TextContent]:
    bootstrap = await client.get_bootstrap()
    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    picks = []
    chips = []
    transfers = {}
    is_authenticated = True

    try:
        my_team = await client.get_my_team()
        picks = my_team.get("picks", [])
        chips = my_team.get("chips", [])
        transfers = my_team.get("transfers", {})
    except Exception:
        is_authenticated = False
        events = bootstrap["events"]
        current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
        try:
            entry_picks = await client.get_entry_picks(gw=current_gw)
            picks = entry_picks.get("picks", [])
            chips = []
        except Exception:
            # Fallback to local state snapshot if pre-season or unauthenticated
            from pathlib import Path
            state_dir = Path("agent/state")
            squad_files = sorted(state_dir.glob("squad-gw*.json"), reverse=True) if state_dir.exists() else []
            if squad_files:
                try:
                    squad_data = json.loads(squad_files[0].read_text(encoding="utf-8"))
                    local_squad = squad_data.get("squad", [])
                    picks = [{"element": p["id"], "position": i + 1, "is_captain": False, "is_vice_captain": False, "multiplier": 1} for i, p in enumerate(local_squad)]
                    chips = squad_data.get("chips", [])
                    transfers = squad_data.get("transfers", {})
                except Exception:
                    picks = []
            
            if not picks:
                entry_info = await client.get_entry()
                return _text({
                    "team_id": entry_info.get("id"),
                    "team_name": entry_info.get("name"),
                    "manager": f"{entry_info.get('player_first_name')} {entry_info.get('player_last_name')}",
                    "overall_points": entry_info.get("summary_overall_points"),
                    "overall_rank": entry_info.get("summary_overall_rank"),
                    "status": "Team overview fetched. Squad picks unlock as gameweek starts, or provide FPL_API_TOKEN for live unconfirmed squad.",
                })

    enriched = []
    for pick in picks:
        el = players_by_id.get(pick["element"], {})
        enriched.append({
            "element_id": pick["element"],
            "name": el.get("web_name", "?"),
            "full_name": f"{el.get('first_name', '')} {el.get('second_name', '')}".strip(),
            "team": teams.get(el.get("team"), "?"),
            "position": POSITION_MAP.get(el.get("element_type"), "?"),
            "price": el.get("now_cost", 0) / 10,
            "status": el.get("status", "?"),
            "news": el.get("news", ""),
            "form": el.get("form", "0"),
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            "multiplier": pick.get("multiplier", 1),
            "position_order": pick.get("position"),
            "starting": pick.get("position", 15) <= 11,
        })

    return _text({
        "squad": enriched,
        "bank": transfers.get("bank", 0) / 10 if is_authenticated else None,
        "team_value": transfers.get("value", 0) / 10 if is_authenticated else None,
        "free_transfers": transfers.get("limit", 1) if is_authenticated else None,
        "transfers_made": transfers.get("made", 0) if is_authenticated else None,
        "chips": chips,
        "mode": "live_private" if is_authenticated else "public_gameweek_picks",
    })


async def _get_entry_info(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    entry = await client.get_entry(team_id=args.get("team_id"))
    return _text({
        "team_id": entry["id"],
        "team_name": entry["name"],
        "player_name": f"{entry['player_first_name']} {entry['player_last_name']}",
        "overall_points": entry["summary_overall_points"],
        "overall_rank": entry["summary_overall_rank"],
        "gw_points": entry["summary_event_points"],
        "gw_rank": entry["summary_event_rank"],
        "team_value": (entry["last_deadline_value"] / 10) if entry.get("last_deadline_value") is not None else 100.0,
        "bank": (entry["last_deadline_bank"] / 10) if entry.get("last_deadline_bank") is not None else 0.0,
        "total_transfers": entry.get("last_deadline_total_transfers", 0),
        "leagues": {
            "classic": [
                {"id": l["id"], "name": l["name"], "rank": l["entry_rank"]}
                for l in entry.get("leagues", {}).get("classic", [])
            ],
            "h2h": [
                {"id": l["id"], "name": l["name"]}
                for l in entry.get("leagues", {}).get("h2h", [])
            ],
        },
    })


async def _get_gw_picks(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    gw = args["gameweek"]
    picks_data = await client.get_entry_picks(gw=gw, team_id=args.get("team_id"))
    bootstrap = await client.get_bootstrap()
    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    picks = picks_data.get("picks", [])
    entry_history = picks_data.get("entry_history", {})
    active_chip = picks_data.get("active_chip")

    enriched = []
    for pick in picks:
        el = players_by_id.get(pick["element"], {})
        enriched.append({
            "element_id": pick["element"],
            "name": el.get("web_name", "?"),
            "team": teams.get(el.get("team"), "?"),
            "position": POSITION_MAP.get(el.get("element_type"), "?"),
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            "multiplier": pick.get("multiplier", 1),
            "starting": pick.get("position", 15) <= 11,
        })

    return _text({
        "gameweek": gw,
        "active_chip": CHIP_NAMES.get(active_chip, active_chip),
        "points": entry_history.get("points"),
        "total_points": entry_history.get("total_points"),
        "rank": entry_history.get("rank"),
        "transfers_cost": entry_history.get("event_transfers_cost", 0),
        "picks": enriched,
    })


async def _get_season_history(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    history = await client.get_entry_history(team_id=args.get("team_id"))
    current = history.get("current", [])
    return _text({
        "season_history": [
            {
                "gameweek": gw["event"],
                "points": gw["points"],
                "total_points": gw["total_points"],
                "rank": gw["rank"],
                "overall_rank": gw["overall_rank"],
                "bank": gw["bank"] / 10,
                "value": gw["value"] / 10,
                "transfers": gw["event_transfers"],
                "transfers_cost": gw["event_transfers_cost"],
                "chip": gw.get("chip"),
            }
            for gw in current
        ],
        "chips_used": history.get("chips", []),
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
