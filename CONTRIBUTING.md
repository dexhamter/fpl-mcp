# Contributing to FPL MCP

Thank you for your interest in improving FPL MCP! We welcome bug reports, feature suggestions, and pull requests.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dexhamter/fpl-mcp.git
   cd fpl-mcp
   ```

2. **Install dependencies using `uv`:**
   ```bash
   uv sync
   ```

3. **Configure your environment:**
   ```bash
   cp .env.example .env
   ```
   Add your `FPL_TEAM_ID` (and optionally `FPL_EMAIL`/`FPL_PASSWORD` or `FPL_COOKIE`).

4. **Run the server locally:**
   ```bash
   uv run fpl-mcp
   ```

## Adding New Tools

- Each tool module lives under `src/fpl_mcp/tools/`.
- Register new tools in `src/fpl_mcp/tools/registry.py`.
- Ensure all public FPL API calls use `client._cached()` with appropriate TTL constants from `constants.py`.

## Guidelines

- Keep tools **read-only** by default to prevent accidental point deductions or unplanned transfers.
- Follow PEP 8 and use type hints throughout.
- Keep output payloads concise so LLMs can process them without overflowing context limits.

## License

By contributing to this project, you agree that your contributions will be licensed under the [MIT License](LICENSE).
