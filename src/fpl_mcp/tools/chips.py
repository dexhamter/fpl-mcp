"""Chips tools — status, usage history, timing advice."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient
from ..constants import CHIP_NAMES

TOOLS = [
    types.Tool(
        name="get_chip_status",
        description=(
            "Return which chips you have used (with GW played) and which are still available. "
            "Chips: Wildcard (x2), Free Hit, Bench Boost, Triple Captain."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_chip_advice",
        description=(
            "Return strategic advice for when to play your remaining chips, "
            "based on upcoming fixture difficulty and GW context."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "next_n": {
                    "type": "integer",
                    "description": "Number of upcoming GWs to analyse (default: 10)",
                    "default": 10,
                }
            },
        },
    ),
]

ALL_CHIPS = {"wildcard", "freehit", "bboost", "3xc"}


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_chip_status":
        return await _get_chip_status(client)
    if name == "get_chip_advice":
        return await _get_chip_advice(arguments, client)
    return None


async def _get_chip_status(client: FPLClient) -> list[types.TextContent]:
    history = await client.get_entry_history()
    chips_used = history.get("chips", [])

    used = {}
    for chip in chips_used:
        cn = chip.get("name")
        if cn not in used:
            used[cn] = []
        used[cn].append(chip.get("event"))

    # Wildcard can be used twice (once in each half of season)
    wildcards_used = len(used.get("wildcard", []))
    wildcards_available = max(0, 2 - wildcards_used)

    result = {
        "chips_used": [
            {
                "chip": CHIP_NAMES.get(chip["name"], chip["name"]),
                "gameweek": chip["event"],
            }
            for chip in chips_used
        ],
        "chips_remaining": {
            "Wildcard": wildcards_available,
            "Free Hit": 0 if "freehit" in used else 1,
            "Bench Boost": 0 if "bboost" in used else 1,
            "Triple Captain": 0 if "3xc" in used else 1,
        },
    }
    return _text(result)


async def _get_chip_advice(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    next_n = args.get("next_n", 10)
    chip_status = await _get_chip_status(client)
    status_data = json.loads(chip_status[0].text)
    remaining = status_data["chips_remaining"]

    bootstrap = await client.get_bootstrap()
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
    future_gws = [e for e in events if e["id"] >= current_gw][: next_n]

    # Analyse DGW / BGW from fixtures
    all_fixtures = await client.get_fixtures()
    gw_team_counts: dict[int, dict[int, int]] = {}
    for f in all_fixtures:
        gw = f.get("event")
        if gw is None:
            continue
        gw_team_counts.setdefault(gw, {})
        for t in [f["team_h"], f["team_a"]]:
            gw_team_counts[gw][t] = gw_team_counts[gw].get(t, 0) + 1

    dgw_gws = [
        gw for gw, counts in gw_team_counts.items()
        if any(c > 1 for c in counts.values())
        and gw >= current_gw
    ]
    bgw_gws = [
        gw for gw, counts in gw_team_counts.items()
        if sum(counts.values()) < 16  # fewer than 8 games = BGW
        and gw >= current_gw
    ]

    advice = []
    if remaining.get("Bench Boost", 0) > 0:
        if dgw_gws:
            advice.append({
                "chip": "Bench Boost",
                "recommendation": f"Play in GW{min(dgw_gws)} (Double Gameweek — bench players get double fixtures).",
                "upcoming_dgws": dgw_gws[:5],
            })
        else:
            advice.append({"chip": "Bench Boost", "recommendation": "Hold until a Double Gameweek is confirmed."})

    if remaining.get("Triple Captain", 0) > 0:
        if dgw_gws:
            advice.append({
                "chip": "Triple Captain",
                "recommendation": f"Play in GW{min(dgw_gws)} on a premium player with a DGW and easy fixtures.",
                "upcoming_dgws": dgw_gws[:5],
            })
        else:
            advice.append({"chip": "Triple Captain", "recommendation": "Hold until a Double Gameweek for maximum return."})

    if remaining.get("Free Hit", 0) > 0:
        if bgw_gws:
            advice.append({
                "chip": "Free Hit",
                "recommendation": f"Play in GW{min(bgw_gws)} (Blank Gameweek) to field a full scoring squad.",
                "upcoming_bgws": bgw_gws[:5],
            })
        else:
            advice.append({"chip": "Free Hit", "recommendation": "Hold for a Blank Gameweek or a gameweek with many injuries in your squad."})

    if remaining.get("Wildcard", 0) > 0:
        advice.append({
            "chip": "Wildcard",
            "recommendation": (
                "Use when your squad needs a major overhaul (>3-4 bad players), "
                "before a price surge window, or to reshape for DGW/BGW swings."
            ),
        })

    return _text({
        "current_gameweek": current_gw,
        "chips_remaining": remaining,
        "detected_dgws": sorted(dgw_gws),
        "detected_bgws": sorted(bgw_gws),
        "advice": advice,
        "note": "DGW/BGW detection is based on fixture data and may not be confirmed by the Premier League yet.",
    })


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
