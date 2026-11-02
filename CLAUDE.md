# CLAUDE.md

Factory Inventory Management System Demo with GitHub integration - Full-stack application with Vue 3 frontend, Python FastAPI backend, and in-memory mock data (no database).

> ⚠️ **This repository and any fork you create are PUBLIC.** Do not commit credentials, internal hostnames, or private registry URLs. `client/.npmrc` pins the public npm registry and `client/package-lock.json` is gitignored to prevent locally-configured registries from leaking into commits — leave both in place.

## Critical Tool Usage Rules

### Subagents
Use the Task tool with these specialized subagents for appropriate tasks:

- **vue-expert**: Use for Vue 3 frontend features, UI components, styling, and client-side functionality
  - Examples: Creating components, fixing reactivity issues, performance optimization, complex state management
  - **MANDATORY RULE: ANY time you need to create or significantly modify a .vue file, you MUST delegate to vue-expert**
- **code-reviewer**: Use after writing significant code to review quality and best practices
- **Explore**: Use for understanding codebase structure, searching for patterns, or answering questions about how components work
- **general-purpose**: Use for complex multi-step tasks or when other agents don't fit

### Skills
- **backend-api-test** skill: Use when writing or modifying tests in `tests/backend` directory with pytest and FastAPI TestClient

### MCP Tools
- **ALWAYS use GitHub MCP tools** (`mcp__github__*`) for ALL GitHub operations
  - Exception: Local branches only - use `git checkout -b` instead of `mcp__github__create_branch`
- **ALWAYS use Playwright MCP tools** (`mcp__playwright__*`) for browser testing
  - Test against: `http://localhost:3000` (frontend), `http://localhost:8001` (API)

## Stack
- **Frontend**: Vue 3 + Composition API + Vite (port 3000)
- **Backend**: Python FastAPI (port 8001)
- **Data**: JSON files in `server/data/` loaded via `server/mock_data.py`

## Quick Start

```bash
# Backend
cd server
uv run python main.py

# Frontend
cd client
npm install && npm run dev
```

## Commands

```bash
./scripts/start.sh                 # start both servers (logs in /tmp/inventory-*.log); ./scripts/stop.sh to stop
cd client && npm run build         # production build -> client/dist/ (no lint or JS test runner is configured)
cd tests && uv run pytest          # all backend tests (pytest.ini sets testpaths=backend)
cd tests && uv run pytest backend/test_inventory.py::TestInventoryEndpoints::test_get_all_inventory   # single test
```

- Backend deps are managed by `uv` (`server/pyproject.toml`; `requirements.txt` mirrors the runtime deps only, not the pytest dev deps). Without `uv`, use `python3 -m venv server/.venv && server/.venv/bin/pip install -r server/requirements.txt`.
- `client/package.json` requires Node `^20.19.0 || >=22.12.0`.
- Tests import `main` by inserting `server/` into `sys.path` (see `tests/backend/conftest.py`), so they run against the real in-memory data, not fixtures.
- `server/generate_data.py` regenerates the JSON files in `server/data/`.

## Architecture Notes

- **Backend is two files**: `server/main.py` (all routes, Pydantic models, and filter helpers `filter_by_month` / `apply_filters`) and `server/mock_data.py` (loads every `server/data/*.json` into module-level lists at import time). Filters use `'all'` as the "no filter" sentinel; `month` accepts `YYYY-MM` or `Q1-2025`-style quarters via `QUARTER_MAP` and matches on `order_date`.
- **Frontend has no store**: filter state is a module-level singleton in `composables/useFilters.js` (period, location, category, status), shared by every view; `getCurrentFilters()` maps it to API params (`period` -> `month`, `location` -> `warehouse`). Routes are declared in `client/src/main.js`. Each view fetches its own data via `api.js`.
- **API base URL is hardcoded** to `http://localhost:8001/api` in `client/src/api.js`; CORS in `main.py` allows all origins.
- **i18n and currency**: `composables/useI18n.js` (en/ja, `t('dotted.key')`, falls back to English, locale persisted in localStorage) also drives currency (en -> USD, ja -> JPY). Backend values are always USD; convert only at display time via `utils/currency.js` (fixed 150 JPY/USD). New UI strings need keys in both `locales/en.js` and `locales/ja.js`.
- **Mock user** in `composables/useAuth.js` is client-side only (no auth endpoints).
- **Known gap**: `api.js` calls `/api/tasks` (GET/POST/PATCH/DELETE) and `/api/purchase-orders`, but `server/main.py` currently defines no such routes (only the `PurchaseOrder` models and `purchase_orders` data used for `has_purchase_order` on `/api/backlog`). Add the routes before relying on those client methods. `/api/reports/*` endpoints exist but are not listed under API Endpoints below.
- `client/CLAUDE.md` and `server/CLAUDE.md` hold detailed frontend/backend conventions; read them when working in those directories.

## Key Patterns

**Filter System**: 4 filters (Time Period, Warehouse, Category, Order Status) apply to all data via query params
**Data Flow**: Vue filters → `client/src/api.js` → FastAPI → In-memory filtering → Pydantic validation → Computed properties
**Reactivity**: Raw data in refs (`allOrders`, `inventoryItems`), derived data in computed properties

## API Endpoints
- `GET /api/inventory` - Filters: warehouse, category
- `GET /api/orders` - Filters: warehouse, category, status, month
- `GET /api/dashboard/summary` - All filters
- `GET /api/demand`, `/api/backlog` - No filters
- `GET /api/spending/*` - Summary, monthly, categories, transactions
- `POST /api/restocking/orders` - Submit a restocking order (prices and lead time are looked up server-side from `/api/demand` data)
- `GET /api/restocking/orders` - Submitted restocking orders, newest first (in memory, reset on restart)

## Common Issues
1. Use unique keys in v-for (not `index`) - use `sku`, `month`, etc.
2. Validate dates before `.getMonth()` calls
3. Update Pydantic models when changing JSON data structure
4. Inventory filters don't support month (no time dimension)
5. Revenue goals: $800K/month single, $9.6M YTD all months

## File Locations
- Views: `client/src/views/*.vue`
- API Client: `client/src/api.js`
- Backend: `server/main.py`, `server/mock_data.py`
- Data: `server/data/*.json`
- Styles: `client/src/App.vue`

## Code Conventions
- Always document non-obvious logic changes with comments

## Design System
- Colors: Slate/gray (#0f172a, #64748b, #e2e8f0)
- Status: green/blue/yellow/red
- Charts: Custom SVG, CSS Grid for layouts
- No emojis in UI
