"""
TEST/DEV UTILITY — never invoked automatically by the app, a deploy, or a
migration. Must be run manually from the command line, and only ever touches
the two seeded demo institutions (never arbitrary or real accounts/data).

Populates the kind of transactional data you only get once someone has
actually used the product: an approved weekly menu plan for each demo
institution, plus the supplier produce orders and farmer demand signals
that approving a menu automatically generates.

It reuses the exact same service functions the live API endpoints call
(menus.services.generate_menu_plan and orders.services.
generate_orders_and_demand_signals) — so the data it creates is produced by
the real "generate menu" / "approve menu" code path, not a hand-rolled
imitation of it.

Usage:
    python manage.py seed_test_scenario
    python manage.py seed_test_scenario --week-start 2026-08-03
    python manage.py seed_test_scenario --reset   # removes the test data again

Safe to run repeatedly — each run first cleans up any test data it
previously created for that same institution/week before regenerating,
so you never end up with duplicate orders or demand signals.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from institutions.models import Institution
from menus.models import MenuPlan
from menus.services import generate_menu_plan
from orders.services import generate_orders_and_demand_signals

# Deliberately hard-coded to the two accounts created by seed_demo_data.
# This command will never touch an institution outside this list, no matter
# what data exists in the database — that's what keeps it safe to run
# against a database that might also contain real usage.
DEMO_INSTITUTION_USERNAMES = ["greenvalley_school", "hopewell_hospital"]


def _upcoming_monday():
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


class Command(BaseCommand):
    help = (
        "TEST DATA ONLY. Generates an approved weekly menu plan (+ resulting "
        "supplier orders and farmer demand signals) for the seeded demo "
        "institutions, using the same code path as the real 'approve menu' "
        "flow. Only ever touches the demo accounts created by seed_demo_data. "
        "Use --reset to remove this test data again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--week-start", type=str, default=None,
            help="ISO date (YYYY-MM-DD) for the menu week. Defaults to the upcoming Monday.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Remove previously generated test-scenario data instead of creating it.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        institutions = list(Institution.objects.filter(user__username__in=DEMO_INSTITUTION_USERNAMES))
        if not institutions:
            raise CommandError(
                "No demo institutions found. Run `python manage.py seed_demo_data` first — "
                "this command only ever populates test data on top of that base seed."
            )

        if options["week_start"]:
            try:
                y, m, d = (int(p) for p in options["week_start"].split("-"))
                week_start = date(y, m, d)
            except ValueError:
                raise CommandError("--week-start must be in YYYY-MM-DD format.")
        else:
            week_start = _upcoming_monday()

        if options["reset"]:
            self._reset(institutions, week_start)
            return

        for institution in institutions:
            self._clear_existing(institution, week_start)
            plan = generate_menu_plan(institution, week_start)
            generate_orders_and_demand_signals(plan)
            order_count = plan.orders.count()
            signal_count = plan.demand_signals.count()
            self.stdout.write(self.style.SUCCESS(
                f"  {institution.name}: approved menu for week of {week_start} "
                f"-> {order_count} supplier order(s), {signal_count} demand signal(s)."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\nTest scenario seeded. Log in as any demo account (see seed_demo_data "
            "output for credentials) to explore the populated dashboards.\n"
            "Run with --reset any time to remove this test data again."
        ))

    def _clear_existing(self, institution, week_start):
        """Remove any test-scenario data this command previously created for
        this institution/week, so re-running never produces duplicates.
        Orders and demand signals use SET_NULL on their menu_plan FK by
        design (so real historical records survive edits elsewhere), so we
        delete them explicitly rather than relying on cascade."""
        existing = MenuPlan.objects.filter(institution=institution, week_start=week_start).first()
        if existing:
            existing.orders.all().delete()
            existing.demand_signals.all().delete()
            # generate_menu_plan() itself replaces the MenuPlan row (replace_existing=True)

    def _reset(self, institutions, week_start):
        removed_any = False
        for institution in institutions:
            plan = MenuPlan.objects.filter(institution=institution, week_start=week_start).first()
            if not plan:
                self.stdout.write(f"  {institution.name}: no test scenario data for week of {week_start}.")
                continue
            plan.orders.all().delete()
            plan.demand_signals.all().delete()
            plan.delete()
            removed_any = True
            self.stdout.write(self.style.SUCCESS(f"  {institution.name}: test scenario data removed."))
        if removed_any:
            self.stdout.write(self.style.SUCCESS("\nDone. Base demo accounts (from seed_demo_data) are untouched."))
