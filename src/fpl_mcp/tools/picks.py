"""Differential and captaincy pick tools."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_captain_suggestions",
        description=(
            "Suggest the best captain pick for the upcoming gameweek based on: "
            "form, fixture difficulty, ICT index, and home/away advantage. "
            "Returns ranked list with reasoning."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "from_my_squad": {
                    "type": "boolean",
                    "description": "If true, only suggest from your current 15 players (default: true)",
                    "default": True,
                },
                "gameweek": {
                    "type": "integer",
                    "description": "Gameweek to target (defaults to next GW)",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of suggestions to return (default: 5)",
                    "default": 5,
                },
            },
        },
    ),
    types.Tool(
        name="get_differentials",
        description=(
            "Return high-potential, low-ownership players — the 'differentials'. "
            "These are players with good form and fixtures but owned by fewer managers, "
            "giving you a rank advantage if they perform well."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "max_ownership": {
                    "type": "number",
                    "description": "Max ownership % to qualify as a differential (default: 15)",
                    "default": 15.0,
                },
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "max_price": {
                    "type": "number",
                    "description": "Max price in £M (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number to return (default: 20)",
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="get_ownership_stats",
        description=(
            "Return ownership percentages and transfer trends for players. "
            "Shows net transfers in/out this GW and price change info."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["ownership", "transfers_in", "transfers_out", "net_transfers"],
                    "description": "Sort field (default: ownership)",
                    "default": "ownership",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default: 30)",
                    "default": 30,
                },
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_captain_suggestions":
        return await _get_captain_suggestions(arguments, client)
    if name == "get_differentials":
        return await _get_differentials(arguments, client)
    if name == "get_ownership_stats":
        return await _get_ownership_stats(arguments, client)
    return None


async def _get_captain_suggestions(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    from_my_squad = args.get("from_my_squad", True)
    top_n = args.get("top_n", 5)

    bootstrap = await client.get_bootstrap()
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
    next_gw = args.get("gameweek") or current_gw

    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    # Get candidate players
    if from_my_squad:
        try:
            my_team = await client.get_my_team()
            my_ids = {p["element"] for p in my_team.get("picks", []) if p.get("position", 15) <= 11}
            candidates = [e for e in bootstrap["elements"] if e["id"] in my_ids]
        except Exception:
            try:
                entry_picks = await client.get_entry_picks(gw=current_gw)
                my_ids = {p["element"] for p in entry_picks.get("picks", []) if p.get("position", 15) <= 11}
                candidates = [e for e in bootstrap["elements"] if e["id"] in my_ids]
            except Exception:
                candidates = sorted(
                    bootstrap["elements"], key=lambda e: e["total_points"], reverse=True
                )[:100]
    else:
        # Top 100 by points
        candidates = sorted(
            bootstrap["elements"], key=lambda e: e["total_points"], reverse=True
        )[:100]

    # Build FDR for next GW per team
    fixtures = await client.get_fixtures(gw=next_gw)
    team_fixture: dict[int, dict] = {}
    for f in fixtures:
        h, a = f["team_h"], f["team_a"]
        team_fixture[h] = {
            "fdr": f["team_h_difficulty"],
            "is_home": True,
            "opp": teams.get(a, "?"),
        }
        team_fixture[a] = {
            "fdr": f["team_a_difficulty"],
            "is_home": False,
            "opp": teams.get(h, "?"),
        }

    scored = []
    for e in candidates:
        if e["status"] not in ("a", "d"):
            continue
        fix = team_fixture.get(e["team"], {})
        fdr = fix.get("fdr", 3)
        is_home = fix.get("is_home", False)
        form = float(e["form"] or 0)
        ict = float(e["ict_index"] or 0)
        ppg = float(e["points_per_game"] or 0)
        # Captaincy score: weighted form, ICT, PPG, boosted for home, penalised for high FDR
        score = (form * 2 + ict * 0.3 + ppg * 1.5) * (6 - fdr) / 5 * (1.1 if is_home else 1.0)
        scored.append((score, e, fix))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        {
            "rank": i + 1,
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "form": e["form"],
            "ict_index": e["ict_index"],
            "points_per_game": e["points_per_game"],
            "opponent": fix.get("opp", "TBC"),
            "home_away": "H" if fix.get("is_home") else "A",
            "fdr": fix.get("fdr"),
            "captaincy_score": round(score, 3),
            "ownership": e["selected_by_percent"],
            "status": e["status"],
        }
        for i, (score, e, fix) in enumerate(scored[:top_n])
    ]
    return _text({
        "gameweek": next_gw,
        "from_squad": from_my_squad,
        "captain_suggestions": results,
        "note": "Score = (form*2 + ICT*0.3 + PPG*1.5) x fixture_ease x home_bonus. Check team news before deciding.",
    })


async def _get_differentials(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    max_own = args.get("max_ownership", 15.0)
    position = args.get("position")
    max_price = args.get("max_price")
    limit = args.get("limit", 20)

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)

    # FDR for next 3 GWs
    all_fixtures = await client.get_fixtures()
    future_gws = list(range(current_gw, current_gw + 3))
    team_fdr: dict[int, list[int]] = {}
    for f in all_fixtures:
        if f.get("event") not in future_gws:
            continue
        h, a = f["team_h"], f["team_a"]
        team_fdr.setdefault(h, []).append(f["team_h_difficulty"])
        team_fdr.setdefault(a, []).append(f["team_a_difficulty"])
    avg_fdr = {tid: sum(v) / len(v) for tid, v in team_fdr.items() if v}

    elements = [
        e for e in bootstrap["elements"]
        if e["status"] == "a"
        and float(e["selected_by_percent"] or 0) <= max_own
    ]
    if position:
        pid = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position)
        elements = [e for e in elements if e["element_type"] == pid]
    if max_price:
        elements = [e for e in elements if e["now_cost"] / 10 <= max_price]

    scored = []
    for e in elements:
        fdr = avg_fdr.get(e["team"], 3.0)
        form = float(e["form"] or 0)
        ppg = float(e["points_per_game"] or 0)
        own = float(e["selected_by_percent"] or 0)
        score = (form * 0.6 + ppg * 0.4) * (6 - fdr) / 5
        scored.append((score, e, fdr))

    scored.sort(key=lambda x: x[0], reverse=True)
    return _text({
        "filters": {"max_ownership": max_own, "position": position, "max_price": max_price},
        "differentials": [
            {
                "rank": i + 1,
                "id": e["id"],
                "name": e["web_name"],
                "team": teams.get(e["team"], "?"),
                "position": POSITION_MAP.get(e["element_type"], "?"),
                "price": e["now_cost"] / 10,
                "ownership": e["selected_by_percent"],
                "form": e["form"],
                "points_per_game": e["points_per_game"],
                "avg_fdr_next_3": round(fdr, 2),
                "score": round(score, 3),
            }
            for i, (score, e, fdr) in enumerate(scored[:limit])
        ],
    })


async def _get_ownership_stats(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    position = args.get("position")
    sort_by = args.get("sort_by", "ownership")
    limit = args.get("limit", 30)

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    if position:
        pid = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position)
        elements = [e for e in elements if e["element_type"] == pid]

    rows = [
        {
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "ownership": float(e["selected_by_percent"] or 0),
            "transfers_in": e["transfers_in_event"],
            "transfers_out": e["transfers_out_event"],
            "net_transfers": e["transfers_in_event"] - e["transfers_out_event"],
            "price_change_gw": e["cost_change_event"] / 10,
        }
        for e in elements
    ]

    sort_key = {
        "ownership": lambda r: r["ownership"],
        "transfers_in": lambda r: r["transfers_in"],
        "transfers_out": lambda r: r["transfers_out"],
        "net_transfers": lambda r: r["net_transfers"],
    }.get(sort_by, lambda r: r["ownership"])

    rows.sort(key=sort_key, reverse=True)
    return _text({"sorted_by": sort_by, "players": rows[:limit]})


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
