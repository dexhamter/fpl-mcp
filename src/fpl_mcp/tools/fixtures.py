"""Fixtures tools — upcoming and completed fixtures with FDR."""

import json
from typing import Any

import mcp.types as types

from ..client import FPLClient

TOOLS = [
    types.Tool(
        name="get_fixtures",
        description=(
            "Return fixtures for a specific gameweek, or all fixtures if no GW is specified. "
            "Each fixture includes home/away team, kickoff time, and result if finished."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "gameweek": {
                    "type": "integer",
                    "description": "Gameweek number (1-38). Omit for all fixtures.",
                }
            },
        },
    ),
    types.Tool(
        name="get_team_fixtures",
        description=(
            "Return upcoming fixtures for a specific team, with fixture difficulty rating (FDR). "
            "Useful for assessing schedule difficulty for transfers and captaincy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Team name or partial name (case-insensitive)",
                },
                "next_n": {
                    "type": "integer",
                    "description": "Number of upcoming fixtures to return (default: 6)",
                    "default": 6,
                },
            },
            "required": ["team_name"],
        },
    ),
    types.Tool(
        name="get_fdr_table",
        description=(
            "Return a fixture difficulty rating (FDR) table for all teams for the next N gameweeks. "
            "Lower FDR = easier fixtures. Great for planning transfers and wildcards."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "next_n": {
                    "type": "integer",
                    "description": "Number of gameweeks ahead to include (default: 6)",
                    "default": 6,
                }
            },
        },
    ),
]


async def handle(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent] | None:
    if name == "get_fixtures":
        return await _get_fixtures(arguments, client)
    if name == "get_team_fixtures":
        return await _get_team_fixtures(arguments, client)
    if name == "get_fdr_table":
        return await _get_fdr_table(arguments, client)
    return None


async def _get_fixtures(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    gw = args.get("gameweek")
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    raw = await client.get_fixtures(gw=gw)
    fixtures = [_format_fixture(f, teams) for f in raw]
    return _text(fixtures)


async def _get_team_fixtures(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    query = args["team_name"].lower()
    next_n = args.get("next_n", 6)

    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t for t in bootstrap["teams"]}
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)

    # Find team by name
    team = next(
        (t for t in teams.values() if query in t["name"].lower() or query in t["short_name"].lower()),
        None,
    )
    if not team:
        return _text({"error": f"No team found matching '{args['team_name']}'"})

    team_id = team["id"]
    all_fixtures = await client.get_fixtures()
    upcoming = [
        f for f in all_fixtures
        if not f["finished"]
        and (f["team_h"] == team_id or f["team_a"] == team_id)
        and f.get("event", 0) >= current_gw
    ]
    upcoming.sort(key=lambda f: f.get("event", 99))
    upcoming = upcoming[:next_n]

    result = []
    for f in upcoming:
        is_home = f["team_h"] == team_id
        opponent_id = f["team_a"] if is_home else f["team_h"]
        fdr = f["team_h_difficulty"] if is_home else f["team_a_difficulty"]
        result.append({
            "gameweek": f.get("event"),
            "kickoff": f.get("kickoff_time"),
            "home_away": "H" if is_home else "A",
            "opponent": teams.get(opponent_id, {}).get("name", "Unknown"),
            "opponent_short": teams.get(opponent_id, {}).get("short_name", "?"),
            "fdr": fdr,
            "fdr_label": _fdr_label(fdr),
        })
    return _text({"team": team["name"], "fixtures": result})


async def _get_fdr_table(
    args: dict, client: FPLClient
) -> list[types.TextContent]:
    next_n = args.get("next_n", 6)
    bootstrap = await client.get_bootstrap()
    teams = {t["id"]: t for t in bootstrap["teams"]}
    events = bootstrap["events"]
    current_gw = next((e["id"] for e in events if e.get("is_current")), 1)
    future_gws = list(range(current_gw, current_gw + next_n))

    all_fixtures = await client.get_fixtures()

    table = {}
    for team_id, team in teams.items():
        table[team_id] = {
            "team": team["name"],
            "short": team["short_name"],
            "gws": {},
        }

    for f in all_fixtures:
        gw = f.get("event")
        if gw not in future_gws:
            continue
        h, a = f["team_h"], f["team_a"]
        if h in table:
            table[h]["gws"][gw] = {"opp": teams[a]["short_name"] + " (H)", "fdr": f["team_h_difficulty"]}
        if a in table:
            table[a]["gws"][gw] = {"opp": teams[h]["short_name"] + " (A)", "fdr": f["team_a_difficulty"]}

    rows = sorted(table.values(), key=lambda r: sum(r["gws"].get(g, {}).get("fdr", 3) for g in future_gws))
    return _text({"gameweeks": future_gws, "fdr_table": rows})


def _format_fixture(f: dict, teams: dict) -> dict:
    return {
        "id": f["id"],
        "gameweek": f.get("event"),
        "kickoff": f.get("kickoff_time"),
        "home_team": teams.get(f["team_h"], str(f["team_h"])),
        "away_team": teams.get(f["team_a"], str(f["team_a"])),
        "home_score": f.get("team_h_score"),
        "away_score": f.get("team_a_score"),
        "finished": f["finished"],
        "home_fdr": f.get("team_h_difficulty"),
        "away_fdr": f.get("team_a_difficulty"),
    }


def _fdr_label(fdr: int) -> str:
    return {1: "Very Easy", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Very Hard"}.get(fdr, "Unknown")


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
