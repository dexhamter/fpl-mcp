"""Price change prediction tools."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import POSITION_MAP

TOOLS = [
    types.Tool(
        name="get_price_risers",
        description=(
            "Return players who are likely to increase in price soon, "
            "based on net transfer activity this gameweek. "
            "FPL prices rise when a player is heavily transferred in."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default: 20)",
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="get_price_fallers",
        description=(
            "Return players who are likely to fall in price, "
            "based on net transfer activity (more being sold than bought)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                    "description": "Filter by position (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default: 20)",
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="get_price_changes",
        description=(
            "Return players whose price has already changed this gameweek "
            "and players whose price has changed since the season started."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["rises", "falls", "all"],
                    "description": "Filter by direction of price change (default: all)",
                    "default": "all",
                },
                "since": {
                    "type": "string",
                    "enum": ["this_gw", "season_start"],
                    "description": "Time window (default: this_gw)",
                    "default": "this_gw",
                },
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_price_risers":
        return await _get_price_movers(arguments, client, direction="rise")
    if name == "get_price_fallers":
        return await _get_price_movers(arguments, client, direction="fall")
    if name == "get_price_changes":
        return await _get_price_changes(arguments, client)
    return None


async def _get_price_movers(
    args: dict, client: FPLClient, direction: str
) -> list[types.TextContent]:
    position = args.get("position")
    limit = args.get("limit", 20)

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    if position:
        pid = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position)
        elements = [e for e in elements if e["element_type"] == pid]

    # Net transfers = in - out. Positive = potential riser, Negative = potential faller
    if direction == "rise":
        movers = [
            e for e in elements
            if e["transfers_in_event"] > e["transfers_out_event"]
        ]
        movers.sort(
            key=lambda e: e["transfers_in_event"] - e["transfers_out_event"],
            reverse=True,
        )
    else:
        movers = [
            e for e in elements
            if e["transfers_out_event"] > e["transfers_in_event"]
        ]
        movers.sort(
            key=lambda e: e["transfers_out_event"] - e["transfers_in_event"],
            reverse=True,
        )

    result = [
        {
            "rank": i + 1,
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "current_price": e["now_cost"] / 10,
            "price_change_this_gw": e["cost_change_event"] / 10,
            "transfers_in": e["transfers_in_event"],
            "transfers_out": e["transfers_out_event"],
            "net_transfers": e["transfers_in_event"] - e["transfers_out_event"],
            "ownership": e["selected_by_percent"],
        }
        for i, e in enumerate(movers[:limit])
    ]
    label = "price_risers" if direction == "rise" else "price_fallers"
    return _text({
        label: result,
        "note": (
            "FPL price changes are based on net transfer activity vs total ownership. "
            "Actual price changes are published by FPL and cannot be predicted with 100% accuracy."
        ),
    })


async def _get_price_changes(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    direction = args.get("direction", "all")
    since = args.get("since", "this_gw")

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    change_field = "cost_change_event" if since == "this_gw" else "cost_change_start"
    label = "this_gw" if since == "this_gw" else "since_season_start"

    elements = [
        e for e in bootstrap["elements"]
        if e[change_field] != 0
    ]
    if direction == "rises":
        elements = [e for e in elements if e[change_field] > 0]
    elif direction == "falls":
        elements = [e for e in elements if e[change_field] < 0]

    elements.sort(key=lambda e: abs(e[change_field]), reverse=True)

    result = [
        {
            "id": e["id"],
            "name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "position": POSITION_MAP.get(e["element_type"], "?"),
            "current_price": e["now_cost"] / 10,
            f"change_{label}": e[change_field] / 10,
            "ownership": e["selected_by_percent"],
        }
        for e in elements
    ]
    return _text({f"price_changes_{label}": result})


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
