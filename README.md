# SokoPulse

AI-assisted nutrition optimization and procurement platform for institutional kitchens
(schools, hospitals, canteens) — connected to the suppliers and farmers who feed them.

This is the full-stack, production-oriented implementation of the SokoPulse product
documented separately: a **Django REST API** backend and a **React + TypeScript**
frontend, styled with a warm, agricultural design system — a sage-green, terracotta,
and amber palette with Playfair Display (display) and Plus Jakarta Sans (body)
typography, built around a componentized layout system (collapsible sidebar, stat
strips, filterable tables, modal-based detail views) shared across the platform.

---

## What's included

- **AI features, powered by Groq** (see dedicated section below) — product
  recommendations, AI-generated weekly menus, supplier market insights, farmer
  planting insights, and an in-app conversational assistant. There is no
  rule-based fallback: every feature calls Groq directly and surfaces a clear
  error if it can't complete.
- **An admin panel** (`/admin/`) for operational configuration — the Groq API
  key/model, the platform procurement margin, and support contact details are
  all managed there, with no redeploy needed (see "Admin panel" below).
- **Role-based dashboards** for three distinct user types, each seeing only what's
  relevant to them:
  - **Institutions** — dietary profile setup, one-click weekly menu generation,
    menu approval → automatic supplier ordering, and compliance reporting.
  - **Suppliers** — manage ingredient listings & pricing, view and update incoming
    orders from institutions.
  - **Farmers** — see forward-looking demand signals generated from real approved
    menus, and commit supply ahead of the delivery window.
- **A general/public site** (home, "how it works", "about & nutrition info") that
  needs no account — general information for anyone, per the product brief.
- **JWT authentication** with role-aware registration and protected routing.
- **A menu-generation engine** implementing the documented heuristic optimizer:
  it balances nutrition targets, per-meal budget, dietary restrictions, and
  ingredient availability, and is designed so a real solver (PuLP / OR-Tools)
  can be swapped in behind the same interface later.
- **Automatic order + demand-signal generation**: approving a menu plan fans out
  into supplier-specific produce orders (with a platform margin — 8% by default,
  configurable in the admin panel) and farmer-facing demand signals, in one
  transaction.
- Seed data: two demo institutions, two suppliers, two farmers, 18 ingredients,
  and 9 recipes, ready to explore immediately — plus an optional, separate
  command to populate realistic test *transactions* (an approved menu →
  resulting orders → resulting demand signals) on top of that, for QA/demo
  purposes (see "Test data for QA / demos" below).

---

## AI features (Groq)

SokoPulse integrates [Groq](https://groq.com) as its AI layer, used across all three
roles. **There is no rule-based fallback** — every AI feature calls Groq directly.
If the key is missing or invalid, or the request fails for any reason, the feature
returns a clear error instead of silently substituting a different result.

### Setup

The Groq API key and related settings are managed from the **admin panel**, not
environment variables:

1. Create a superuser if you don't have one: `python manage.py createsuperuser`
2. Log in at `/admin/` and open **Configuration → System configuration**
3. Paste your key from [console.groq.com](https://console.groq.com) into
   **Groq api key**, adjust the model/timeout if needed, and save

That's it — no redeploy, no `.env` edit, no code change. (For a first deploy from
a fresh environment, `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_TIMEOUT_SECONDS`
environment variables are used to *seed* the row the very first time it's created,
purely for convenience — after that, the admin panel is always the source of truth.)

### What the AI does, by role

**Institutions**
- **Product recommendations** (`POST /api/ai/recommend-products/`) — given the
  institution's dietary profile, restrictions, headcount, and either its default
  budget or a one-off override, the AI selects a basket of ingredients from active
  supplier listings that balances nutrition against the most *favourable* (cost-
  effective) pricing available. Institutions can accept the basket as-is, deselect
  items they don't want, or skip this step entirely and pick products manually from
  the full supplier catalogue instead — both paths are first-class in the UI's
  **Smart menu builder** (Menu planner page).
- **AI-generated weekly menu** (`POST /api/ai/generate-weekly-menu/`) — once a
  product basket is confirmed (AI-recommended or hand-picked), the AI builds a full
  7-day breakfast/lunch/dinner table using *only* those products, balanced against
  daily nutrition targets. The institution reviews the table and, if happy, approves
  it — which flows through the exact same order + demand-signal pipeline as the
  original heuristic engine (see below), so nothing else about the system had to
  change to support this.
- The original one-click **heuristic generator** (recipe-library based, no product
  selection needed) is still available side-by-side as a "quick generate" option.

**Suppliers**
- **AI market insights** (`GET /api/ai/supplier-insights/`) — cross-references a
  supplier's own listings against recent institutional demand signals and competitor
  pricing, surfacing which products are in high demand, which are priced
  uncompetitively, and where there's a clear opportunity to expand.

**Farmers**
- **AI planting insights** (`GET /api/ai/farmer-insights/`) — analyses demand-signal
  trends in the farmer's county (rising/falling/stable) against their existing supply
  commitments, highlighting the biggest uncommitted gaps worth prioritising.

**Everyone**
- **In-app conversational assistant** — a floating "Ask SokoPulse AI" widget on every
  dashboard (`POST /api/ai/ask/`), answering account-specific questions using only
  the requesting user's own context (their institution's profile and latest plan,
  their listings, their demand signals — never another account's data).

### Error handling — no fallback, by design

Every AI function in `ai_engine/services.py` calls Groq directly and lets
failures propagate as `ai_engine.groq_client.GroqUnavailable`. The view layer
(`ai_engine/views.py`) turns that into a `503` response:

- In **development** (`DJANGO_DEBUG=True`), the response includes the real
  exception, so you can see exactly what went wrong (missing key, network
  error, malformed response, etc).
- In **production** (`DJANGO_DEBUG=False`), the response is a generic
  "AI service is temporarily unavailable" message — no internals are leaked,
  and no substitute result is generated.

The frontend surfaces whichever message the backend sends, in an inline error
state with a retry button (see `components/ui.tsx` → `ErrorState`).

---

## Admin panel

Visit `/admin/` and log in with a superuser account
(`python manage.py createsuperuser` if you don't have one yet). Under
**Configuration → System configuration** you can manage, without a redeploy:

| Setting | Purpose |
|---|---|
| Groq api key | Required for every AI feature — see "AI features" above |
| Groq model | Defaults to `llama-3.3-70b-versatile` |
| Groq timeout seconds | How long to wait for Groq before treating a call as failed |
| Platform margin percent | The procurement margin applied to produce orders (default 8%) |
| Support email | Shown to users / used for notifications |
| Site name | Displayed name for the platform |

This is a singleton settings row — the admin always jumps straight to editing
it rather than showing a list.

---

## Project structure

```
sokopulse/
├── backend/           Django REST API
│   ├── accounts/       custom User model, JWT auth, role-aware registration
│   ├── institutions/    Institution, Site, DietaryProfile
│   ├── suppliers/       Supplier, SupplierListing
│   ├── farmers/         Farmer, DemandSignal, SupplyCommitment
│   ├── nutrition/       Ingredient, Recipe, RecipeIngredient + cost/nutrition utils
│   ├── menus/           MenuPlan, MenuItem + the menu-generation engine
│   ├── orders/          ProduceOrder, ProduceOrderItem + order-generation service
│   ├── ai_engine/       Groq client + AI recommendation/menu/insights/assistant services
│   ├── configuration/   Admin-managed SystemConfiguration (Groq key/model, platform margin, etc.)
│   └── core/            public stats, compliance reports, seed_demo_data +
│                        seed_test_scenario management commands
└── frontend/           React + TypeScript (Vite) SPA
    ├── src/api/          typed API client (axios + JWT refresh)
    ├── src/auth/         auth context + protected routes
    ├── src/components/   shared UI, public layout, dashboard shell
    └── src/pages/        public/, institution/, supplier/, farmer/
```

---

## Backend setup

Requires Python 3.11+.

```bash
cd backend
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo_data   # optional but recommended — creates demo accounts below
python manage.py runserver        # http://localhost:8000
```

By default the backend uses **SQLite** (zero config — `python manage.py migrate`
creates a fresh, empty `db.sqlite3` locally; it is not committed to the repo).
To point it at PostgreSQL instead (recommended for production, and what the
product documentation specifies), set these environment variables before
running migrate:

```bash
export POSTGRES_DB=sokopulse
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=yourpassword
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

Other useful environment variables (all optional, sensible defaults are used):

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key | dev key (change in production) |
| `DJANGO_DEBUG` | Debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins | `http://localhost:5173,...` |

The Django admin is available at `/admin/` (login: `admin` / `admin12345` after seeding).

### Demo accounts (created by `seed_demo_data`)

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin12345` |
| Institution (school) | `greenvalley_school` | `demo12345` |
| Institution (hospital) | `hopewell_hospital` | `demo12345` |
| Supplier | `kiambu_fresh_growers` | `demo12345` |
| Supplier | `nairobi_grain_traders` | `demo12345` |
| Farmer | `john_mwangi_farm` | `demo12345` |
| Farmer | `mary_wanjiru_farm` | `demo12345` |

---

## Test data for QA / demos

`seed_demo_data` (above) only creates *accounts and catalogue data* — institutions,
suppliers, farmers, ingredients, recipes. It deliberately does **not** create any
menu plans, orders, or demand signals, so a freshly seeded database still looks
exactly like a brand-new account with nobody having used it yet.

For QA or demoing, it's often useful to see the dashboards *populated* — an
approved weekly menu, the supplier orders it generated, the farmer demand signals
it generated. A second, separate command does exactly that:

```bash
python manage.py seed_test_scenario                       # upcoming Monday
python manage.py seed_test_scenario --week-start 2026-08-03
python manage.py seed_test_scenario --reset                # remove it again
python manage.py seed_test_scenario --week-start 2026-08-03 --reset
```

This is a **test-only utility**, and is built to be safe to hand to anyone on the
team:

- **It is never invoked automatically** — not on `migrate`, not on deploy, not by
  any other command. It only ever runs if someone explicitly types it.
- **It is hard-scoped to the two demo institutions** (`greenvalley_school`,
  `hopewell_hospital`) at the code level — it cannot touch a real institution's
  account or data, no matter what else exists in the database.
- **It reuses the real production code path** — the exact same
  `generate_menu_plan()` / `generate_orders_and_demand_signals()` functions the
  live "Generate menu" and "Approve" API endpoints call — so the data it produces
  is indistinguishable from data a real user would have created.
- **It's idempotent**: re-running it for the same week cleans up what it created
  last time first, so you never end up with duplicate orders or demand signals.
- **`--reset` removes exactly what it added** (that institution/week's menu plan,
  orders, and demand signals) and nothing else — any other data in the database,
  demo or real, is left untouched.

After running it, log in as `greenvalley_school` / `demo12345` and you'll see a
populated Overview, an approved plan under Menu planner, and orders under Produce
orders — and the corresponding supplier/farmer accounts will show the orders and
demand signals it generated.

---

## Frontend setup

Requires Node.js 18+.

```bash
cd frontend
npm install
cp .env.example .env   # adjust VITE_API_URL if your backend isn't on localhost:8000
npm run dev             # http://localhost:5173
```

To build for production:

```bash
npm run build     # outputs to dist/
npm run preview   # serve the production build locally
```

---

## Trying it out end-to-end

*(Want the dashboards pre-populated instead of doing this by hand? Run
`python manage.py seed_test_scenario` and skip to step 6.)*

1. Start the backend (`python manage.py runserver`) and frontend (`npm run dev`).
2. Visit `http://localhost:5173` — the general/public site needs no login.
3. Log in as `greenvalley_school` / `demo12345` (institution).
4. Go to **Menu planner**. In the **Smart menu builder**, either:
   - Click **Get AI recommendations** (optionally set a budget override first), review
     the suggested basket, deselect anything you don't want, then click
     **Generate weekly menu from these products**; or
   - Choose **"I'll choose products myself"**, pick items from the catalogue, then
     generate the menu from your own selection.
   - (Or skip all of this and click **Quick generate** for the original one-click
     recipe-library menu.)
5. Expand the generated plan and click **Approve & place orders**.
6. Log in as `kiambu_fresh_growers` / `demo12345` (supplier) to see the resulting
   order under **Incoming orders**, and check **AI market insights** for pricing and
   demand intelligence on your listings.
7. Log in as `john_mwangi_farm` / `demo12345` (farmer) to see the resulting
   **Demand signals**, commit supply against one, and check **AI planting insights**
   for county-level demand trends.
8. Try the **"Ask SokoPulse AI"** floating widget on any dashboard for account-aware
   Q&A.

---

## Notes on the menu-generation engine

The optimizer (`backend/menus/services.py`) is implemented as a fast, dependency-free
greedy heuristic: for each meal slot in the week it scores every eligible recipe
against the institution's per-meal nutrition share and budget, and avoids repeating
the same main dish within a short window. This matches the "solver with a documented
fallback" behaviour described in the product spec, and is intentionally isolated
behind a single `generate_menu_plan()` function so a true linear/integer programming
solver (PuLP, OR-Tools) can be substituted later without touching the API or frontend.

## Production hardening checklist

This build is functionally complete and ready to develop against, but before a real
deployment you should also:
- Switch `DEBUG=False`, set a real `DJANGO_SECRET_KEY`, and configure `DJANGO_ALLOWED_HOSTS`.
- Point the database at PostgreSQL (see above) and enable regular backups.
- Serve the Django app behind Gunicorn/Uvicorn + a reverse proxy (Nginx), not `runserver`.
- Build the frontend (`npm run build`) and serve the static `dist/` output via a CDN
  or the same reverse proxy.
- Move ingredient/QR/media storage to object storage (e.g. S3-compatible) if you add
  file uploads (lab documents, produce photos, etc.).
- Add HTTPS/TLS termination at the proxy or load balancer.
- Never run `seed_demo_data` or `seed_test_scenario` against a production database —
  both are development/QA utilities. `seed_demo_data` refuses to run twice (it exits
  if an `admin` user already exists) but was written for local/staging use, not as
  a production onboarding flow.
