# ⚽ FPL MCP — Model Context Protocol Server for Fantasy Premier League

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Standard](https://img.shields.io/badge/MCP-1.0%2B-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with uv](https://img.shields.io/badge/package%20manager-uv-purple.svg)](https://docs.astral.sh/uv/)

An asynchronous **Model Context Protocol (MCP)** server for **Fantasy Premier League (FPL)**. Equips AI coding assistants and agent frameworks (Antigravity, Claude Desktop, Cursor, Custom Agents) with **33 dedicated tools** to analyze fixtures, scout differentials, manage squads, track live scores, monitor price fluctuations, and optimize transfers and captaincy decisions.

---

## 🌟 Key Features

- **🚀 33 Specialized Tools**: Complete coverage of official FPL endpoints (Bootstrap, Fixtures, FDR, Squad, History, Chips, Live Gameweek Scores, Mini-Leagues, Set-Piece Takers, Differentials, and Price Movers).
- **🔒 Safe & Read-Only**: Focuses on deep analytics and AI recommendations without risky automated transfers.
- **⚡ In-Memory TTL Caching**: Intelligent per-endpoint caching prevents rate limiting from FPL servers while keeping live gameweek scores fresh.
- **🛡️ Public & Private Support**: Works immediately for public data with just a team ID. Supports modern Bearer token authentication (`FPL_API_TOKEN` / `x-api-authorization`) for private squad and live pick access.
- **🔌 Standard stdio Transport**: Plug-and-play with any MCP-compliant client.

---

## 🏗️ Architecture

```
fpl-mcp/
├── src/fpl_mcp/
│   ├── server.py          # MCP Server entrypoint (stdio transport)
│   ├── client.py          # Async FPL HTTP client with TTL caching
│   ├── auth.py            # Bearer token & session manager
│   ├── cache.py           # In-memory thread-safe TTL cache
│   ├── constants.py       # API endpoints, TTLs, positions & chip maps
│   └── tools/
│       ├── registry.py    # Aggregator & dynamic tool dispatcher
│       ├── bootstrap.py   # Players, teams, and season status
│       ├── fixtures.py    # Fixtures schedule & FDR matrix
│       ├── squad.py       # Team picks, history, and manager info
│       ├── players.py     # Deep player statistics (xG, xA, ICT, PPG)
│       ├── transfers.py   # Transfer history, bank, and AI transfer scout
│       ├── chips.py       # Chip tracker & Double/Blank GW strategy engine
│       ├── live.py        # Real-time provisional GW scores & bonus points
│       ├── leagues.py     # Classic & Head-to-Head mini-league tables
│       ├── news.py        # Injury reports, bans, and set-piece takers
│       ├── picks.py       # Algorithmically ranked captain picks & differentials
│       └── prices.py      # Predicted price risers/fallers & confirmed changes
├── pyproject.toml
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or `pip`

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/dexhamter/fpl-mcp.git
cd fpl-mcp

# Install dependencies into virtual environment
uv sync
```

### 3. Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` with your team information:
```ini
# Your FPL Team ID (found in the URL: https://fantasy.premierleague.com/entry/{ID}/event/1)
FPL_TEAM_ID=1234567

# Preferred auth: Bearer JWT copied from browser
FPL_API_TOKEN=eyJhbGciOi...

# Legacy fallbacks / optional persistence (cookie or session file)
# FPL_COOKIE=
# FPL_SESSION_FILE=fpl_session.json
```

#### 🔑 How to Get Your `FPL_API_TOKEN`
FPL uses Bearer token authentication via the `x-api-authorization` header rather than legacy `pl_profile` login cookies. To authenticate for private squad and live unconfirmed team data:
1. Log in to [fantasy.premierleague.com](https://fantasy.premierleague.com).
2. Open your browser DevTools (`F12` or Right-Click -> **Inspect**) and switch to the **Network** tab.
3. Refresh the page or click **Pick Team** / **Transfers** / **Points**.
4. Filter network requests by `api/` or `Fetch/XHR` and click any request (e.g., `my-team/...`).
5. Under **Request Headers**, find `x-api-authorization`.
6. Copy the token string (strip the leading `Bearer ` prefix).
7. Paste it into your `.env` file as `FPL_API_TOKEN=...`.

> [!NOTE]
> `FPL_API_TOKEN` typically expires every ~8 hours. If private endpoints return `401 Unauthorized`, simply copy a fresh token from DevTools.

---

## ⚙️ Connecting to MCP Clients

### 🤖 Antigravity / Gemini CLI
Add the server to your `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "fpl": {
      "command": "C:/Users/your_user/Documents/fpl/.venv/Scripts/python.exe",
      "args": ["-m", "fpl_mcp.server"],
      "env": {
        "PYTHONPATH": "C:/Users/your_user/Documents/fpl/src",
        "FPL_TEAM_ID": "1234567",
        "FPL_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

### 🟣 Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "fpl": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/fpl-mcp",
        "run",
        "fpl-mcp"
      ],
      "env": {
        "FPL_TEAM_ID": "1234567",
        "FPL_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

### 💻 Cursor / Windsurf
In Settings -> Features -> MCP Servers:
- **Type**: `command`
- **Command**: `uv --directory /path/to/fpl-mcp run fpl-mcp`

---

## 🛠️ Tool Catalog (33 Tools)

### 1. General & Bootstrap Data
| Tool | Arguments | Description |
|---|---|---|
| `get_all_players` | `position`, `team`, `max_price`, `min_form` | Query all active players with filtering & sorting |
| `search_player` | `query` (required) | Search for players by partial or full name |
| `get_all_teams` | None | Get all 20 Premier League teams with strength ratings |
| `get_game_settings` | None | Gameweek deadline, average score, top managers |

### 2. Fixtures & Difficulty (FDR)
| Tool | Arguments | Description |
|---|---|---|
| `get_fixtures` | `gameweek` | All or specific gameweek match schedules |
| `get_team_fixtures` | `team_name` (required), `next_n` | Upcoming schedule for a team with FDR ratings |
| `get_fdr_table` | `next_n` | Comparative FDR grid across all teams |

### 3. Squad & Manager Overview
| Tool | Arguments | Description |
|---|---|---|
| `get_my_squad` | None | Current 15-player squad, starters, bench, captaincy |
| `get_entry_info` | `team_id` | Overall rank, total points, bank balance, and team value |
| `get_gw_picks` | `gameweek` (required), `team_id` | Squad lineup for any completed gameweek |
| `get_season_history` | `team_id` | Gameweek-by-gameweek rank and point trajectory |

### 4. Player Analytics
| Tool | Arguments | Description |
|---|---|---|
| `get_player_stats` | `player_id`, `player_name` | xG, xA, ICT index, bonus points, minutes, form |
| `get_player_history` | `player_id`, `player_name` | Detailed per-gameweek match log for a player |
| `get_top_performers` | `sort_by`, `position`, `max_price`, `limit` | Ranked leaderboard by points, form, PPG, or ICT |

### 5. Transfers & Budget
| Tool | Arguments | Description |
|---|---|---|
| `get_transfer_history` | `team_id` | Full season transfer log with buy/sell costs |
| `get_bank_balance` | None | Available in-the-bank funds, free transfers, team value |
| `get_transfer_suggestions` | `position`, `max_price`, `next_n_gws` | Composite algorithm scouting transfers by form & FDR |

### 6. Chips Strategy
| Tool | Arguments | Description |
|---|---|---|
| `get_chip_status` | None | Tracker for Wildcards, Free Hit, Bench Boost, Triple Captain |
| `get_chip_advice` | `next_n` | Double/Blank Gameweek detection and optimal chip timing |

### 7. Live Gameweek Scores
| Tool | Arguments | Description |
|---|---|---|
| `get_live_gw_scores` | `gameweek`, `sort_by`, `limit` | Real-time provisional player points, goals, assists |
| `get_my_live_score` | `gameweek` | Real-time running total for your squad with active captain multiplier |

### 8. Mini-Leagues & Standings
| Tool | Arguments | Description |
|---|---|---|
| `get_my_leagues` | None | All classic and head-to-head mini-leagues for your team |
| `get_classic_league_standings` | `league_id` (required), `page` | Full leaderboard table with ranks and event scores |
| `get_h2h_league_standings` | `league_id` (required), `page` | Head-to-head records (W/D/L, match points) |

### 9. Team News & Set Pieces
| Tool | Arguments | Description |
|---|---|---|
| `get_player_news` | `status` | Filter players with injuries, suspensions, or doubts |
| `get_set_piece_takers` | `team_name` | Designated penalty, free-kick, and corner takers |
| `check_my_squad_news` | None | Health check across your 15 players with status alerts |

### 10. Captaincy & Differentials
| Tool | Arguments | Description |
|---|---|---|
| `get_captain_suggestions` | `from_my_squad`, `gameweek`, `top_n` | Multi-factor weighted captain score (Form, ICT, FDR, Home) |
| `get_differentials` | `max_ownership`, `position`, `max_price` | High-potential low-ownership picks (<15% default) |
| `get_ownership_stats` | `position`, `sort_by`, `limit` | Ownership %, transfer momentum, and net delta |

### 11. Price Movements
| Tool | Arguments | Description |
|---|---|---|
| `get_price_risers` | `position`, `limit` | Imminent price risers based on net incoming transfers |
| `get_price_fallers` | `position`, `limit` | Imminent price fallers based on net outgoing transfers |
| `get_price_changes` | `direction`, `since` | Confirmed price alterations this gameweek or season |

---

## 💡 Example Assistant Prompts

Once configured with your agent, you can ask natural language questions like:
- *"Who should I captain for Gameweek 1? Compare my best options based on fixtures and expected goal involvement."*
- *"Check my squad for any injury concerns before the deadline."*
- *"I have £0.5m in the bank and need to replace a midfielder under £7.5m with easy upcoming fixtures. Who do you suggest?"*
- *"Show me the top 5 differential forwards owned by less than 10% of managers."*
- *"Who is on penalty duties for Arsenal and Liverpool this season?"*
- *"What is our strategy for Double and Blank Gameweeks? When should I consider using my Bench Boost?"*

---

## ⏱️ Caching Policy

To preserve low latency and comply with FPL server etiquette, data is cached in-memory:

| Endpoint Type | Default TTL |
|---|---|
| Live Gameweek Scores (`live.py`) | 60 seconds |
| Squad & Entry Info (`squad.py`) | 120 - 300 seconds |
| Bootstrap & Player Stats (`bootstrap.py`, `players.py`) | 300 seconds (5 min) |
| Fixtures & Schedule (`fixtures.py`) | 600 seconds (10 min) |

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## ⚽ Disclaimer

This tool is not officially affiliated with or endorsed by the Premier League or Fantasy Premier League. All data is fetched from public FPL API endpoints.
