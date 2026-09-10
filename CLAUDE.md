# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local FastAPI + Jinja2 + SQLite + vanilla-JS dashboard that supports KEPCO's information
disclosure (정보공개청구/FOIA) request workflow: 접수(intake) → AI identifies the request
target and flags repeat requests → a dispatcher assigns a staff member → that staff member
runs a legal decision wizard (grounded in specific 정보공개법 articles) → a final notice is
issued. The decision graph itself is `docs/blueprint.jpeg` encoded as data in
`app/services/foia_core.py::FLOW_STEPS`.

The stack and design system are deliberately reused from a sibling project
(`../scada_system_agent`). A hard constraint drives many design choices here: **the app must
run on a 10-year-old server or console PC** (`docs/DEVELOPMENT_STANDARD.md` §5) — Python
3.8+, minimal external packages, no bundler/build step, works from plain `cmd`/PowerShell.
That's why the frontend is one plain `<script>`-tag JS file with no module system, and why
`requirements.txt` pins exact versions instead of ranges.

## Commands

```bash
# Dev run (auto-reload)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Easiest run for a non-dev user: double-click 실행.bat (installs deps, opens browser)

# Tests
pip install -r requirements-dev.txt   # pytest only — not installed in production
pytest                                  # whole suite
pytest tests/test_recommend.py          # one file
pytest tests/test_recommend.py::test_engines_registry_has_all_backends   # one test
FOIA_SKIP_AI_SERVER=1 pytest            # already set by tests/conftest.py; not needed manually

# Retrain the two ML recommendation engines (writes into data/models/*.joblib)
python tools/train_gbm_recommender.py
python tools/train_xgboost_recommender.py

# Standardized change-log entry (see docs/DEVELOPMENT_STANDARD.md)
python tools/log_change.py --ticket FOIA-00NN --summary "..." --type fix|feat|docs|refactor|test|config
```

No linter/formatter/build step is configured — `python -m compileall app tools` is the
closest thing to a static check the project standard mentions.

## Architecture

### Module split (`app/`)

`app/main.py` only wires things up (FastAPI instance, `lifespan` seeding, the single global
auth middleware, router registration). It used to hold *everything* (1,000+ lines); it was
split into:
- `app/security.py` — authentication (session cookie signing/verification, pbkdf2 password
  hashing, login-attempt lockout) *and* authorization (`require_role` for page routes,
  `require_role_api` for JSON routes, CSRF token issuance/verification). Both a page route and
  its matching API route independently re-check the role — there is no single shared gate.
- `app/deps.py` — process-wide singletons (`db`, `ai_client`, `processor`,
  `local_ai_server`, `templates`) that routers import directly, plus small helpers shared by
  multiple routers (`with_deadline`, `load_recommendation`) and `DEFAULT_ACCOUNTS` (the seed
  data for `admin`/`manager`/`dispatcher`/`staff1..staff10`, created lazily in `lifespan` only
  if the username doesn't exist yet — existing passwords are never touched).
- `app/roles.py` — the 4 role-name string constants (Korean role names) and their post-login
  landing pages. Single source of truth so a typo doesn't silently become "no permission".
  Roles: 시스템관리자(ADMIN) / 총괄관리자(MANAGER) / 배정담당자(DISPATCHER) / 업무담당자(STAFF).
- `app/routers/*.py` — one file per screen area (`auth`, `dashboard`, `requests`, `dispatch`,
  `admin`, `settings`). `requests.py` is the biggest: request list/detail/notice pages plus
  the assign/reject/reassign/extend-deadline/decide JSON API.
- `app/db.py` — a single `Database` class wrapping raw SQL (parameterized, no ORM) over 4
  tables: `users`, `disclosure_requests`, `request_decisions` (one row per request, tracks
  wizard progress via `current_step` + boolean columns), `decision_log` (append-only audit
  trail), plus `app_settings`. Methods are grouped by comment banner (`# --- Users ---` etc.).
  Startup runs idempotent `ALTER TABLE ... ADD COLUMN` migrations (`_migrate_*`) rather than a
  migration framework.

### Request-decision engine

`app/services/foia_core.py::FLOW_STEPS` is a dict-shaped state machine: each step has a
label, its legal article, and where `on_yes`/`on_no` lead (either another step key or a final
`notice` type). `advance(step_key, answer)` walks it one step; `db.apply_step_answer` persists
the answer and logs it. This is the only place the legal decision logic lives — routers just
call into it.

### AI recommendation engines (`app/services/recommend/`)

A small plugin registry: `ENGINES` (in `__init__.py`) maps a string key to an object
implementing the `Recommender` protocol (`base.py`) — `source: str` + `recommend(row) ->
RecommendResult`. `POST /api/requests/{id}/generate-recommendation` (`routers/requests.py`)
runs *every* registered engine and returns them all side by side; the frontend
(`RECOMMEND_ENGINE_ORDER`/`RECOMMEND_ENGINE_LABELS` in `app/static/js/app.js`) must be kept in
sync with this dict's keys or a working engine's result silently never renders (this has
happened once — see git history).

Currently registered: `gbm` and `xgboost` (both real TF-IDF + sklearn-style classifiers,
trained by `tools/train_gbm_recommender.py` / `tools/train_xgboost_recommender.py`) and `llm`
(interface only — always returns `available: false` until a provider/API-key/privacy decision
is made; the TODO is in `llm_recommender.py`).

Both real engines share infrastructure in `base.py`:
- `CachedModelFile` — loads a joblib model file, keyed by mtime, so retraining takes effect on
  the next request without a server restart (a real bug once shipped here without this).
- `rank_and_filter` — turns `(classes, proba)` into the top-3 *currently active* staff
  accounts (accounts deleted/role-changed since training are dropped even if the model still
  predicts them).
- `lazy_joblib_load` — `joblib` is imported inside this function, not at module top, so a
  broken `joblib`/`xgboost` install disables only the recommend feature, not app startup.

Training data: `tools/_training_data.py` is shared by both training scripts —
`load_training_examples()` prefers real history in `data/training/staff_assignments.csv`
(gitignored — real requester text is personal data) and falls back to
`app/services/recommend/synthetic_data.py`'s keyword-template generator when that file is
absent or empty. `data/training/README.md` documents the CSV format for whoever is filling it
in. As of this writing there is barely any real assignment history, so both models are
trained on synthetic data — their reported "accuracy" reflects how well they learned the
synthetic keyword rules, not real-world performance (this is deliberately *not* shown to end
users — see the `⚠` caveat text baked into every engine's `reason` field).

### Local AI sidecar (`app/ai_runtime/`)

A second, tiny FastAPI app (`api.py`, exposing `/identify`) that does the actual request-target
extraction, repeat-request similarity check (`difflib`), and petition-vs-disclosure
classification (`utils_text.py`) — all rule-based, no external LLM call. `LocalAIServer`
(`app/services/local_ai_server.py`) runs it either in-thread or as a frozen sidecar
executable, and the main app's `AIClient` talks to it over `INTERNAL_AI_API_URL`
(`127.0.0.1:8011` by default). `RequestProcessorService` (`request_processor.py`) is what
actually calls it, when a file lands in the watched intake folder (`data/watch/`).

### Frontend

Server-rendered Jinja2 templates (`app/templates/`) + one global-scope JS file
(`app/static/js/app.js`, organized top-to-bottom by `// ── section ──` banners: utilities →
dashboard rendering → detail-page actions → staff search → reject/reassign flow → AI
recommendation flow → clock/polling → init). No SPA framework, no bundler — functions are
attached to `window` implicitly and wired to elements via inline `onclick=`. There's no
WebSocket/SSE despite `connectSSE()`'s name — it's `setInterval` polling, same as the "new
assignment" toast polling for staff (`pollMyQueue`).

### Auth model

Session = an HMAC-signed cookie (`app/security.py`), not a DB-backed session table. CSRF is a
synchronizer token recomputed from `auth_secret` per request (nothing stored server-side
either). The single `require_authentication` middleware in `main.py` only checks "is there a
valid session for *some* public path", **not** role — every route additionally calls
`require_role`/`require_role_api` itself with the specific roles it allows.

### Tests

`tests/conftest.py` sets `FOIA_*` env vars (temp DB path, `FOIA_SKIP_AI_SERVER=1`, etc.)
**before** importing `app.main` — `app/config.py` reads env vars at import time, so import
order matters if you add new test setup. A session-scoped `_lifespan` fixture seeds accounts
once; each test gets a fresh `TestClient` (via `as_admin`/`as_manager`/`as_dispatcher`/
`as_staff1`/`as_staff2` fixtures) and transactional tables are wiped between tests while
account rows persist for the session. `make_request` inserts a request directly via the `db`
singleton rather than going through the (removed) `/requests/new` endpoint, since the intake
folder scan is now the only normal ingestion path.

### Change-log discipline

This repo tracks every change as `logs/changes/YYYY-MM-DD/FOIA-NNNN-slug.md`
(`tools/log_change.py` generates the template) alongside a `CHANGELOG.md` entry and a commit —
see `docs/DEVELOPMENT_STANDARD.md` for the full convention. `docs/PROJECT_REVIEW.md` is a
living risk/priority list; check it before assuming something is a fresh problem — it may
already be a documented, deliberately-deferred trade-off (e.g. synchronous SQLite calls
blocking the event loop is a known, accepted-for-now issue at current traffic scale).
