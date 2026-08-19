"""Transfer planner tools — history, bank balance, suggestions."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_transfer_history",
        description="Return all transfers made this season: player in, player out, price paid, GW.",
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {"type": "integer", "description": "FPL team ID (defaults to yours)"}
            },
        },
    ),
    types.Tool(
        name="get_bank_balance",
        description="Return your current bank balance, team value, and free transfers available.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_transfer_suggestions",
        description=(
            "Suggest transfer targets based on form, fixture difficulty, price, and "
            "availability. Returns players to bring IN ranked by value, and optionally "
            "players in your squad to consider selling OUT."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Target position for the transfer",
                },
                "max_price": {
                    "type": "number",
                    "description": "Budget ceiling in £M for the incoming player",
                },
                "next_n_gws": {
                    "type": "integer",
                    "description": "Number of upcoming GWs to consider for fixture ease (default: 5)",
                    "default": 5,
                },
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_transfer_history":
        return await _get_transfer_history(arguments, client)
    if name == "get_bank_balance":
        return await _get_bank_balance(client)
    if name == "get_transfer_suggestions":
        return await _get_transfer_suggestions(arguments, client)
    return None


async def _get_transfer_history(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    transfers = await client.get_entry_transfers(team_id=args.get("team_id"))
    bootstrap = await client.get_bootstrap()
    players_by_id = {e["id"]: e["web_name"] for e in bootstrap["elements"]}

    enriched = [
        {
            "gameweek": t["event"],
            "player_in": players_by_id.get(t["element_in"], str(t["element_in"])),
            "player_in_cost": t["element_in_cost"] / 10,
            "player_out": players_by_id.get(t["element_out"], str(t["element_out"])),
            "player_out_cost": t["element_out_cost"] / 10,
        }
        for t in sorted(transfers, key=lambda t: t["event"], reverse=True)
    ]
    return _text({"total_transfers": len(enriched), "transfers": enriched})


async def _get_bank_balance(client: FPLClient) -> list[types.TextContent]:
    my_team = await client.get_my_team()
    transfers = my_team.get("transfers", {})
    return _text({
        "bank": transfers.get("bank", 0) / 10,
        "team_value": transfers.get("value", 0) / 10,
        "free_transfers": transfers.get("limit", 1),
        "transfers_made_this_gw": transfers.get("made", 0),
    })


async def _get_transfer_suggestions(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    position = args.get("position")
    max_price = args.get("max_price")
    next_n = args.get("next_n_gws", 5)

    bootstrap = await client.get_bootstrap()
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
    future_gws = list(range(current_gw, current_gw + next_n))

    # Build FDR lookup: team_id -> average FDR over next_n GWs
    all_fixtures = await client.get_fixtures()
    team_fdr: dict[int, list[int]] = {}
    for f in all_fixtures:
        if f.get("event") not in future_gws or f["finished"]:
            continue
        h, a = f["team_h"], f["team_a"]
        team_fdr.setdefault(h, []).append(f["team_h_difficulty"])
        team_fdr.setdefault(a, []).append(f["team_a_difficulty"])

    avg_fdr = {tid: sum(fdrs) / len(fdrs) for tid, fdrs in team_fdr.items() if fdrs}

    teams_map = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    elements = [
        e for e in bootstrap["elements"]
        if e["status"] == "a"  # available only
    ]

    if position:
        pos_id = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position)
        elements = [e for e in elements if e["element_type"] == pos_id]
    if max_price:
        elements = [e for e in elements if e["now_cost"] / 10 <= max_price]

    scored = []
    for e in elements:
        fdr = avg_fdr.get(e["team"], 3.0)
        form = float(e["form"] or 0)
        ppg = float(e["points_per_game"] or 0)
        # Simple composite score: higher form/ppg, lower FDR = better
        score = (form * 0.5 + ppg * 0.5) * (6 - fdr) / 5
        scored.append((score, e, fdr))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        {
            "rank": i + 1,
            "id": e["id"],
            "name": e["web_name"],
            "team": teams_map.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "form": e["form"],
            "points_per_game": e["points_per_game"],
            "avg_fdr_next_{}_gws".format(next_n): round(fdr, 2),
            "selected_by_percent": e["selected_by_percent"],
            "composite_score": round(score, 3),
        }
        for i, (score, e, fdr) in enumerate(scored[:20])
    ]
    return _text({
        "filters": {"position": position, "max_price": max_price, "gws_ahead": next_n},
        "suggestions": results,
        "note": "Composite score = (form + PPG) weighted by fixture ease. Always verify with team news.",
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
