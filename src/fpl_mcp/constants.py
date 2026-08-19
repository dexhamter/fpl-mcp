"""API base URLs and configuration constants."""

FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_LOGIN_URL = "https://users.premierleague.com/accounts/login/"

# Endpoint templates (plain strings — use .format(**kwargs) at call site)
ENDPOINTS = {
    # Public
    "bootstrap": f"{FPL_BASE}/bootstrap-static/",
    "fixtures": f"{FPL_BASE}/fixtures/",
    "fixtures_gw": f"{FPL_BASE}/fixtures/?event={{gw}}",
    "element_summary": f"{FPL_BASE}/element-summary/{{player_id}}/",
    "event_live": f"{FPL_BASE}/event/{{gw}}/live/",
    "event_status": f"{FPL_BASE}/event-status/",
    # Authenticated
    "me": f"{FPL_BASE}/me/",
    "my_team": f"{FPL_BASE}/my-team/{{team_id}}/",
    "entry": f"{FPL_BASE}/entry/{{team_id}}/",
    "entry_picks": f"{FPL_BASE}/entry/{{team_id}}/event/{{gw}}/picks/",
    "entry_transfers": f"{FPL_BASE}/entry/{{team_id}}/transfers/",
    "entry_history": f"{FPL_BASE}/entry/{{team_id}}/history/",
    "classic_league": f"{FPL_BASE}/leagues-classic/{{league_id}}/standings/",
    "h2h_league": f"{FPL_BASE}/leagues-h2h/{{league_id}}/standings/",
    "h2h_matches": f"{FPL_BASE}/leagues-h2h-matches/league/{{league_id}}/",
}

# Cache TTLs in seconds
TTL = {
    "bootstrap": 300,        # 5 min — player prices, teams
    "fixtures": 600,         # 10 min — fixture list
    "element_summary": 300,  # 5 min — player history
    "event_live": 60,        # 1 min — live GW scores
    "event_status": 60,      # 1 min
    "my_team": 120,          # 2 min — my squad
    "entry": 300,            # 5 min — team info
    "entry_picks": 300,      # 5 min — GW picks
    "entry_transfers": 300,  # 5 min — transfer history
    "entry_history": 300,    # 5 min — season history
    "league": 300,           # 5 min — league standings
}

# Chip names
CHIP_NAMES = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
}

# Position IDs
POSITION_MAP = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}
