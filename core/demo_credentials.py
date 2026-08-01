"""
Single source of truth for the demo/admin credentials used by:
  - render_setup.py            (creates the admin superuser on deploy)
  - seed_conference_demo.py    (creates admin + every demo institution/supplier/farmer account)

Keeping this in one place means the admin account created on deploy (Render, or any other
environment running render_setup.py) always matches the credentials documented in CHANGES.md
and printed by `manage.py seed_conference_demo` — no more drift between the two.
"""

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@sokopulse.app"
ADMIN_PASSWORD = "Conference2026!"

# Password shared by every account seed_conference_demo.py creates (institutions, suppliers, farmers).
# Deliberately the same as ADMIN_PASSWORD so there is exactly one password to remember at the conference.
DEMO_PASSWORD = "Conference2026!"
