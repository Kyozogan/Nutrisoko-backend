"""
ONE-STOP CONFERENCE / SHOWCASE SEED.

Populates the whole platform — admin, institutions, suppliers, farmers,
ingredients, recipes, supplier listings, historical approved menus, produce
orders, demand signals, supply commitments, notifications, and a couple of
billing subscription records — so a presenter can log in and demo the
platform without first clicking through registration forms for every role.

Design goal: everything EXCEPT the AI engine itself is pre-populated, so
during a live demo you only need to show the AI features — product
recommendations, AI weekly menu generation, supplier/farmer AI insights, and
the assistant — working against real, already-interconnected data (multiple
suppliers competing on price for the same ingredients, real demand signals,
real budgets). One institution ("Sunrise Academy") is deliberately left with
no menu plan yet, specifically so you can generate its AI menu live on stage.

This command is fully standalone — it does not depend on seed_demo_data
having been run first — and is idempotent: usernames are fixed, so running
it again simply leaves existing accounts untouched instead of erroring or
duplicating data.

Usage:
    python manage.py seed_conference_demo
    python manage.py seed_conference_demo --reset   # removes everything this command created
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from institutions.models import Institution, DietaryProfile
from suppliers.models import Supplier, SupplierListing
from farmers.models import Farmer, DemandSignal, SupplyCommitment
from nutrition.models import Ingredient, Recipe, RecipeIngredient
from menus.services import generate_menu_plan
from orders.services import generate_orders_and_demand_signals
from billing.models import Subscription
from configuration.models import SystemConfiguration
from core.demo_credentials import ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_PASSWORD

# Every non-admin username this command ever creates — used by --reset to clean up precisely,
# without touching any other data (e.g. accounts from seed_demo_data, or real usage).
INSTITUTION_USERNAMES = [
    "sunrise_academy", "silverline_school", "rift_valley_boarding",
    "hopewell_hospital_demo", "coastal_care_hospital", "kisumu_bay_canteen",
]
SUPPLIER_USERNAMES = [
    "kiambu_fresh_growers_demo", "nairobi_grain_traders_demo", "rift_highlands_produce",
    "mombasa_coastal_suppliers", "kisumu_lakeside_traders", "nakuru_valley_wholesalers",
]
FARMER_USERNAMES = [
    "john_mwangi_demo", "mary_wanjiru_demo", "peter_kiplagat", "amina_hassan",
    "grace_atieno", "samuel_kiprono",
]
ALL_SEED_USERNAMES = INSTITUTION_USERNAMES + SUPPLIER_USERNAMES + FARMER_USERNAMES


def _upcoming_monday():
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


class Command(BaseCommand):
    help = "Populate SokoPulse with a full, interconnected demo dataset across every role — ready for a live conference showcase of the AI engine."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove all data created by this command.")

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()
            return
        with transaction.atomic():
            self._seed()

    # ------------------------------------------------------------------
    def _reset(self):
        deleted, _ = User.objects.filter(username__in=ALL_SEED_USERNAMES).delete()
        self.stdout.write(self.style.SUCCESS(f"Removed conference demo data ({deleted} related rows). Other accounts were left untouched."))

    # ------------------------------------------------------------------
    def _seed(self):
        self.stdout.write("Seeding conference demo data…")

        admin = self._ensure_admin()
        ingredients = self._ensure_ingredients()
        self._ensure_recipes(ingredients)

        institutions = self._ensure_institutions()
        suppliers = self._ensure_suppliers()
        self._ensure_listings(suppliers, ingredients)
        farmers = self._ensure_farmers()

        self._generate_history(institutions)
        self._ensure_commitments(farmers)
        self._ensure_subscriptions(institutions, suppliers)

        cfg = SystemConfiguration.load()
        if cfg.payments_enabled:
            cfg.payments_enabled = False
            cfg.save(update_fields=["payments_enabled"])

        self._print_summary(admin, institutions, suppliers, farmers)

    # ------------------------------------------------------------------
    def _ensure_admin(self):
        admin, created = User.objects.get_or_create(
            username=ADMIN_USERNAME, defaults={"email": ADMIN_EMAIL, "role": "admin", "is_staff": True, "is_superuser": True},
        )
        # Always (re)set a known password — even if an "admin" account already existed (e.g. from
        # seed_demo_data or manual setup) — so the credentials printed at the end of this command
        # are guaranteed to work for the presenter. Also make sure it's flagged as an admin/staff
        # account in case it pre-existed with different flags.
        admin.set_password(ADMIN_PASSWORD)
        admin.email = ADMIN_EMAIL
        admin.role = "admin"
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.save()
        if created:
            self.stdout.write("  Created admin account.")
        else:
            self.stdout.write("  Admin account already existed — password reset to the demo password below.")
        return admin

    # ------------------------------------------------------------------
    def _ensure_ingredients(self):
        data = [
            ("Maize flour", "kg", Ingredient.Category.GRAIN, 3650, 90, 730, 40, 90, False, False, True),
            ("Maize (dry grain)", "kg", Ingredient.Category.GRAIN, 3600, 95, 720, 45, 85, False, False, False),
            ("Wheat flour", "kg", Ingredient.Category.GRAIN, 3640, 100, 760, 15, 130, False, False, True),
            ("Rice", "kg", Ingredient.Category.GRAIN, 3600, 70, 790, 10, 140, False, False, False),
            ("Beans", "kg", Ingredient.Category.LEGUME, 3400, 220, 600, 10, 160, False, False, False),
            ("Kale (Sukuma wiki)", "kg", Ingredient.Category.VEGETABLE, 320, 30, 60, 5, 40, False, False, False),
            ("Cabbage", "kg", Ingredient.Category.VEGETABLE, 250, 10, 60, 1, 35, False, False, False),
            ("Tomatoes", "kg", Ingredient.Category.VEGETABLE, 180, 10, 40, 2, 80, False, False, False),
            ("Onions", "kg", Ingredient.Category.VEGETABLE, 400, 10, 90, 1, 90, False, False, False),
            ("Carrots", "kg", Ingredient.Category.VEGETABLE, 410, 10, 100, 2, 70, False, False, False),
            ("Milk", "l", Ingredient.Category.DAIRY, 610, 32, 48, 32, 70, False, True, False),
            ("Eggs", "dozen", Ingredient.Category.PROTEIN, 840, 72, 6, 60, 360, False, False, False),
            ("Chicken", "kg", Ingredient.Category.PROTEIN, 2390, 270, 0, 140, 450, True, False, False),
            ("Beef", "kg", Ingredient.Category.PROTEIN, 2500, 260, 0, 170, 550, True, False, False),
            ("Fish (Tilapia)", "kg", Ingredient.Category.PROTEIN, 1290, 260, 0, 30, 480, True, False, False),
            ("Cooking oil", "l", Ingredient.Category.FAT, 8840, 0, 0, 1000, 300, False, False, False),
            ("Bananas", "kg", Ingredient.Category.FRUIT, 890, 10, 230, 3, 100, False, False, False),
            ("Mangoes", "kg", Ingredient.Category.FRUIT, 600, 8, 150, 4, 120, False, False, False),
            ("Sweet potatoes", "kg", Ingredient.Category.GRAIN, 860, 20, 200, 1, 80, False, False, False),
            ("Spinach", "kg", Ingredient.Category.VEGETABLE, 230, 30, 40, 4, 60, False, False, False),
            ("Groundnuts", "kg", Ingredient.Category.LEGUME, 5670, 260, 160, 490, 250, False, False, False),
            ("Bread", "loaf", Ingredient.Category.GRAIN, 1060, 36, 196, 12, 70, False, False, True),
            ("Green grams (Ndengu)", "kg", Ingredient.Category.LEGUME, 3470, 240, 630, 12, 175, False, False, False),
            ("Yoghurt", "l", Ingredient.Category.DAIRY, 610, 35, 45, 33, 180, False, True, False),
        ]
        ingredients = {}
        for (name, unit, cat, cal, prot, carb, fat, price, meat, dairy, gluten) in data:
            ing, _ = Ingredient.objects.get_or_create(name=name, defaults=dict(
                unit=unit, category=cat, calories_per_unit=cal, protein_g_per_unit=prot,
                carbs_g_per_unit=carb, fat_g_per_unit=fat, default_price_per_unit=price,
                contains_meat=meat, contains_dairy=dairy, contains_gluten=gluten,
            ))
            ingredients[name] = ing
        self.stdout.write(f"  Ingredients ready ({Ingredient.objects.count()} total).")
        return ingredients

    # ------------------------------------------------------------------
    def _ensure_recipes(self, ing):
        data = [
            ("Uji porridge with bananas", Recipe.MealType.BREAKFAST, [("Maize flour", 0.08), ("Milk", 0.15), ("Bananas", 0.12)]),
            ("Bread, eggs & milk", Recipe.MealType.BREAKFAST, [("Bread", 0.25), ("Eggs", 0.17), ("Milk", 0.2)]),
            ("Sweet potato & groundnut breakfast", Recipe.MealType.BREAKFAST, [("Sweet potatoes", 0.25), ("Groundnuts", 0.03)]),
            ("Mandazi, boiled eggs & sweet tea", Recipe.MealType.BREAKFAST, [("Wheat flour", 0.08), ("Cooking oil", 0.02), ("Eggs", 0.08), ("Milk", 0.15)]),
            ("Ugali, beans & sukuma wiki", Recipe.MealType.LUNCH, [("Maize flour", 0.15), ("Beans", 0.12), ("Kale (Sukuma wiki)", 0.1), ("Cooking oil", 0.01), ("Onions", 0.02), ("Tomatoes", 0.03)]),
            ("Rice & chicken stew", Recipe.MealType.LUNCH, [("Rice", 0.15), ("Chicken", 0.12), ("Tomatoes", 0.05), ("Onions", 0.03), ("Cooking oil", 0.01), ("Carrots", 0.04)]),
            ("Green grams & rice", Recipe.MealType.LUNCH, [("Rice", 0.14), ("Green grams (Ndengu)", 0.12), ("Onions", 0.02), ("Cooking oil", 0.01)]),
            ("Fish & ugali", Recipe.MealType.LUNCH, [("Maize flour", 0.15), ("Fish (Tilapia)", 0.15), ("Tomatoes", 0.04), ("Onions", 0.02), ("Cooking oil", 0.01)]),
            ("Githeri (maize, beans & vegetables)", Recipe.MealType.LUNCH, [("Maize (dry grain)", 0.13), ("Beans", 0.08), ("Onions", 0.02), ("Tomatoes", 0.03), ("Carrots", 0.03), ("Cooking oil", 0.01)]),
            ("Pilau rice with beef", Recipe.MealType.LUNCH, [("Rice", 0.15), ("Beef", 0.1), ("Onions", 0.03), ("Carrots", 0.03), ("Cooking oil", 0.01)]),
            ("Beef & cabbage stew with ugali", Recipe.MealType.DINNER, [("Maize flour", 0.15), ("Beef", 0.1), ("Cabbage", 0.12), ("Onions", 0.02), ("Tomatoes", 0.04), ("Cooking oil", 0.01)]),
            ("Rice, beans & spinach", Recipe.MealType.DINNER, [("Rice", 0.14), ("Beans", 0.12), ("Spinach", 0.1), ("Onions", 0.02), ("Cooking oil", 0.01)]),
            ("Vegetable & egg stew with ugali", Recipe.MealType.DINNER, [("Maize flour", 0.14), ("Eggs", 0.08), ("Carrots", 0.05), ("Cabbage", 0.08), ("Cooking oil", 0.01)]),
            ("Chicken & rice supper", Recipe.MealType.DINNER, [("Rice", 0.13), ("Chicken", 0.1), ("Carrots", 0.04), ("Onions", 0.02), ("Cooking oil", 0.01)]),
            ("Chapati & beef stew", Recipe.MealType.DINNER, [("Wheat flour", 0.1), ("Cooking oil", 0.02), ("Beef", 0.1), ("Onions", 0.02), ("Tomatoes", 0.04)]),
            ("Banana & groundnut snack", Recipe.MealType.SNACK, [("Bananas", 0.1), ("Groundnuts", 0.03)]),
        ]
        for name, meal_type, ing_list in data:
            recipe, created = Recipe.objects.get_or_create(
                name=name, defaults=dict(meal_type=meal_type, portion_size="1 plate",
                                          description=f"{name} — a balanced {meal_type} option built from locally available produce."),
            )
            if created:
                for ing_name, qty in ing_list:
                    RecipeIngredient.objects.create(recipe=recipe, ingredient=ing[ing_name], quantity_per_portion=Decimal(str(qty)))
        self.stdout.write(f"  Recipes ready ({Recipe.objects.count()} total).")

    # ------------------------------------------------------------------
    def _make_institution(self, username, email, name, itype, county, headcount, phone,
                           breakfast=None, lunch=None, supper=None,
                           calories=2000, protein=55, carbs=260, fat=65, restrictions=None, guideline=""):
        user, created = User.objects.get_or_create(
            username=username, defaults=dict(email=email, role="institution", county=county, phone=phone),
        )
        if not created:
            return Institution.objects.get(user=user)
        user.set_password(DEMO_PASSWORD)
        user.save()
        inst = Institution(
            user=user, name=name, type=itype, county=county, headcount=headcount,
            budget_breakfast=breakfast, budget_lunch=lunch, budget_supper=supper, contact_phone=phone,
        )
        if inst.meal_budgets_set():
            inst.recompute_budget_per_meal()
        inst.save()
        DietaryProfile.objects.create(
            institution=inst, target_calories=calories, target_protein_g=protein,
            target_carbs_g=carbs, target_fat_g=fat, restrictions=restrictions or [], guideline_reference=guideline,
        )
        return inst

    def _ensure_institutions(self):
        institutions = {}
        institutions["sunrise"] = self._make_institution(
            "sunrise_academy", "admin@sunriseacademy.ac.ke", "Sunrise Academy", Institution.Type.SCHOOL,
            "Nairobi", 560, "+254701000001", breakfast=Decimal("45"), lunch=Decimal("90"), supper=Decimal("70"),
            calories=1900, protein=50, guideline="Kenya School Meals Programme Guidelines",
        )  # showcase institution — left with NO menu plan, for a live AI demo
        institutions["silverline"] = self._make_institution(
            "silverline_school", "info@silverlineschool.ac.ke", "Silverline Girls Secondary School",
            Institution.Type.SCHOOL, "Nakuru", 480, "+254701000002",
            lunch=Decimal("95"), calories=2000, protein=55, guideline="Kenya School Meals Programme Guidelines",
        )  # lunch-only day school
        institutions["rift_valley"] = self._make_institution(
            "rift_valley_boarding", "kitchen@riftvalleyboarding.ac.ke", "Rift Valley Boarding School",
            Institution.Type.SCHOOL, "Uasin Gishu", 620, "+254701000003",
            breakfast=Decimal("40"), supper=Decimal("65"), calories=2100, protein=58,
            guideline="Kenya School Meals Programme Guidelines",
        )  # boarding school with breakfast + supper, no lunch (day trips)
        institutions["hopewell"] = self._make_institution(
            "hopewell_hospital_demo", "nutrition@hopewell.or.ke", "Hopewell County Hospital",
            Institution.Type.HOSPITAL, "Nairobi", 210, "+254701000004",
            breakfast=Decimal("75"), lunch=Decimal("140"), supper=Decimal("110"),
            calories=2100, protein=60, restrictions=["dairy-free"], guideline="Ministry of Health Patient Nutrition Guidelines",
        )
        institutions["coastal_care"] = self._make_institution(
            "coastal_care_hospital", "catering@coastalcare.or.ke", "Coastal Care Hospital",
            Institution.Type.HOSPITAL, "Mombasa", 160, "+254701000005",
            lunch=Decimal("130"), supper=Decimal("105"),
            calories=2050, protein=58, restrictions=["gluten-free"], guideline="Ministry of Health Patient Nutrition Guidelines",
        )
        institutions["kisumu_bay"] = self._make_institution(
            "kisumu_bay_canteen", "manager@kisumubaycanteen.co.ke", "Kisumu Bay Staff Canteen",
            Institution.Type.CANTEEN, "Kisumu", 140, "+254701000006",
            breakfast=Decimal("50"), lunch=Decimal("85"), calories=2200, protein=60,
        )
        self.stdout.write(f"  Institutions ready ({len(institutions)}).")
        return institutions

    # ------------------------------------------------------------------
    def _make_supplier(self, username, email, name, county, phone):
        user, created = User.objects.get_or_create(
            username=username, defaults=dict(email=email, role="supplier", county=county, phone=phone),
        )
        if not created:
            return Supplier.objects.get(user=user)
        user.set_password(DEMO_PASSWORD)
        user.save()
        return Supplier.objects.create(user=user, name=name, county=county, contact_phone=phone, verified=True)

    def _ensure_suppliers(self):
        suppliers = {}
        suppliers["kiambu"] = self._make_supplier("kiambu_fresh_growers_demo", "sales@kiambufresh.co.ke", "Kiambu Fresh Growers Cooperative", "Kiambu", "+254711000001")
        suppliers["nairobi_grain"] = self._make_supplier("nairobi_grain_traders_demo", "orders@nairobigrain.co.ke", "Nairobi Grain & Protein Traders", "Nairobi", "+254711000002")
        suppliers["rift_highlands"] = self._make_supplier("rift_highlands_produce", "sales@rifthighlands.co.ke", "Rift Highlands Produce", "Uasin Gishu", "+254711000003")
        suppliers["mombasa_coastal"] = self._make_supplier("mombasa_coastal_suppliers", "orders@mombasacoastal.co.ke", "Mombasa Coastal Suppliers", "Mombasa", "+254711000004")
        suppliers["kisumu_lakeside"] = self._make_supplier("kisumu_lakeside_traders", "info@kisumulakeside.co.ke", "Kisumu Lakeside Traders", "Kisumu", "+254711000005")
        suppliers["nakuru_valley"] = self._make_supplier("nakuru_valley_wholesalers", "sales@nakuruvalley.co.ke", "Nakuru Valley Wholesalers", "Nakuru", "+254711000006")
        self.stdout.write(f"  Suppliers ready ({len(suppliers)}).")
        return suppliers

    def _ensure_listings(self, sup, ing):
        """
        Several ingredients are deliberately listed by more than one supplier at different
        prices — that price spread is what makes the AI's 'favourable supplier budget'
        recommendations and the supplier-insights market comparison meaningful to demo.
        """
        rows = [
            # (supplier key, ingredient, price) — same ingredient across rows = competing prices
            ("kiambu", "Kale (Sukuma wiki)", 32), ("kiambu", "Cabbage", 28), ("kiambu", "Tomatoes", 72),
            ("kiambu", "Onions", 82), ("kiambu", "Carrots", 62), ("kiambu", "Bananas", 92),
            ("kiambu", "Sweet potatoes", 72), ("kiambu", "Spinach", 52), ("kiambu", "Mangoes", 115),

            ("nairobi_grain", "Maize flour", 85), ("nairobi_grain", "Rice", 135), ("nairobi_grain", "Beans", 155),
            ("nairobi_grain", "Chicken", 430), ("nairobi_grain", "Beef", 530), ("nairobi_grain", "Eggs", 340),
            ("nairobi_grain", "Cooking oil", 290), ("nairobi_grain", "Milk", 65), ("nairobi_grain", "Groundnuts", 240),
            ("nairobi_grain", "Bread", 65), ("nairobi_grain", "Green grams (Ndengu)", 165),
            ("nairobi_grain", "Wheat flour", 125), ("nairobi_grain", "Maize (dry grain)", 80),

            # Rift Highlands undercuts Kiambu & Nairobi Grain on several overlapping items —
            # the AI should surface these as the more "favourable" option for institutions near it.
            ("rift_highlands", "Maize flour", 78), ("rift_highlands", "Beans", 148), ("rift_highlands", "Kale (Sukuma wiki)", 30),
            ("rift_highlands", "Cabbage", 26), ("rift_highlands", "Carrots", 58), ("rift_highlands", "Milk", 58),
            ("rift_highlands", "Eggs", 320), ("rift_highlands", "Sweet potatoes", 68), ("rift_highlands", "Maize (dry grain)", 75),
            ("rift_highlands", "Wheat flour", 120),

            ("mombasa_coastal", "Fish (Tilapia)", 460), ("mombasa_coastal", "Rice", 128), ("mombasa_coastal", "Cooking oil", 285),
            ("mombasa_coastal", "Mangoes", 95), ("mombasa_coastal", "Bananas", 88), ("mombasa_coastal", "Yoghurt", 165),
            ("mombasa_coastal", "Chicken", 420),

            ("kisumu_lakeside", "Fish (Tilapia)", 440), ("kisumu_lakeside", "Rice", 132), ("kisumu_lakeside", "Green grams (Ndengu)", 158),
            ("kisumu_lakeside", "Tomatoes", 68), ("kisumu_lakeside", "Onions", 78), ("kisumu_lakeside", "Bread", 62),

            ("nakuru_valley", "Beef", 505), ("nakuru_valley", "Milk", 55), ("nakuru_valley", "Yoghurt", 155),
            ("nakuru_valley", "Cooking oil", 275), ("nakuru_valley", "Groundnuts", 225), ("nakuru_valley", "Beans", 150),
            ("nakuru_valley", "Carrots", 55),
        ]
        created_count = 0
        for sup_key, ing_name, price in rows:
            _, created = SupplierListing.objects.get_or_create(
                supplier=sup[sup_key], ingredient=ing[ing_name],
                defaults=dict(price_per_unit=Decimal(str(price)), quantity_available=Decimal("600"),
                              available_from=date.today(), available_to=date.today() + timedelta(days=180)),
            )
            created_count += int(created)
        self.stdout.write(f"  Supplier listings ready ({SupplierListing.objects.count()} total, {created_count} new).")

    # ------------------------------------------------------------------
    def _make_farmer(self, username, email, name, county, crop_focus, phone):
        user, created = User.objects.get_or_create(
            username=username, defaults=dict(email=email, role="farmer", county=county, phone=phone),
        )
        if not created:
            return Farmer.objects.get(user=user)
        user.set_password(DEMO_PASSWORD)
        user.save()
        return Farmer.objects.create(user=user, name=name, county=county, crop_focus=crop_focus, contact_phone=phone)

    def _ensure_farmers(self):
        farmers = {}
        farmers["john"] = self._make_farmer("john_mwangi_demo", "john@farm.co.ke", "John Mwangi", "Kiambu", "Kale, Cabbage, Tomatoes", "+254722000001")
        farmers["mary"] = self._make_farmer("mary_wanjiru_demo", "mary@farm.co.ke", "Mary Wanjiru", "Nairobi", "Beans, Maize", "+254722000002")
        farmers["peter"] = self._make_farmer("peter_kiplagat", "peter@farm.co.ke", "Peter Kiplagat", "Uasin Gishu", "Maize, Milk, Eggs", "+254722000003")
        farmers["amina"] = self._make_farmer("amina_hassan", "amina@farm.co.ke", "Amina Hassan", "Mombasa", "Fish, Mangoes, Bananas", "+254722000004")
        farmers["grace"] = self._make_farmer("grace_atieno", "grace@farm.co.ke", "Grace Atieno", "Kisumu", "Fish, Green grams, Rice", "+254722000005")
        farmers["samuel"] = self._make_farmer("samuel_kiprono", "samuel@farm.co.ke", "Samuel Kiprono", "Nakuru", "Beef, Milk, Groundnuts", "+254722000006")
        self.stdout.write(f"  Farmers ready ({len(farmers)}).")
        return farmers

    # ------------------------------------------------------------------
    def _generate_history(self, institutions):
        """
        Approve a menu (past week, so it reads as settled history rather than something
        still pending) for every institution except 'sunrise' — that one stays untouched
        so its AI weekly-menu generation can be demoed live.
        """
        past_week_start = _upcoming_monday() - timedelta(days=14)
        for key, inst in institutions.items():
            if key == "sunrise":
                continue
            if inst.menu_plans.filter(week_start=past_week_start).exists():
                continue
            plan = generate_menu_plan(inst, past_week_start)
            if plan.status == plan.Status.DRAFT:
                generate_orders_and_demand_signals(plan)
        self.stdout.write(f"  Historical menu plans, produce orders & demand signals generated "
                           f"({len(institutions) - 1} institutions; 'Sunrise Academy' left clean for the live demo).")

    def _ensure_commitments(self, farmers):
        """Farmers in the same county as a demand signal partially commit supply against it —
        leaving some signals fully open so 'unmet demand' is still visible to demo."""
        created = 0
        for farmer in farmers.values():
            open_signals = DemandSignal.objects.filter(
                county__iexact=farmer.county,
            ).exclude(commitments__farmer=farmer)[:2]
            for signal in open_signals:
                already = SupplyCommitment.objects.filter(demand_signal=signal, farmer=farmer).exists()
                if already:
                    continue
                qty = (signal.forecast_quantity * Decimal("0.4")).quantize(Decimal("0.01"))
                if qty <= 0:
                    continue
                SupplyCommitment.objects.create(
                    farmer=farmer, demand_signal=signal, quantity_committed=qty,
                    status=SupplyCommitment.Status.CONFIRMED,
                )
                created += 1
        self.stdout.write(f"  Supply commitments ready ({created} new).")

    def _ensure_subscriptions(self, institutions, suppliers):
        """A couple of active subscription records so the admin Subscriptions page isn't empty."""
        now = timezone.now()
        pairs = [
            (institutions["silverline"].user, "institution", Decimal("5000.00")),
            (suppliers["kiambu"].user, "supplier", Decimal("2500.00")),
        ]
        created = 0
        for user, role, amount in pairs:
            if Subscription.objects.filter(user=user).exists():
                continue
            Subscription.objects.create(
                user=user, role=role, amount=amount,
                reference=f"DEMO-{user.username[:12].upper()}", expires_at=now + timedelta(days=30),
            )
            created += 1
        self.stdout.write(f"  Sample subscriptions ready ({created} new).")

    # ------------------------------------------------------------------
    def _print_summary(self, admin, institutions, suppliers, farmers):
        line = "-" * 78
        self.stdout.write("\n" + self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS("CONFERENCE DEMO — FULL LOGIN CREDENTIALS"))
        self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS(f"Every account below uses the same password:  {ADMIN_PASSWORD}\n"))

        self.stdout.write(self.style.SUCCESS("ADMIN  (log in, then go to /admin-panel)"))
        self.stdout.write(f"  username: {admin.username:<28} password: {ADMIN_PASSWORD}")

        self.stdout.write(self.style.SUCCESS("\nINSTITUTIONS  (log in, then /institution)"))
        inst_notes = {
            "sunrise": "Nairobi — breakfast+lunch+supper — NO menu plan yet: generate one live with the AI",
            "silverline": "Nakuru — lunch only",
            "rift_valley": "Uasin Gishu — breakfast + supper only (no lunch)",
            "hopewell": "Nairobi — breakfast+lunch+supper — dairy-free dietary profile",
            "coastal_care": "Mombasa — lunch + supper — gluten-free dietary profile",
            "kisumu_bay": "Kisumu — breakfast + lunch only",
        }
        for key, inst in institutions.items():
            self.stdout.write(f"  username: {inst.user.username:<28} password: {DEMO_PASSWORD}   {inst.name} — {inst_notes.get(key, '')}")

        self.stdout.write(self.style.SUCCESS("\nSUPPLIERS  (log in, then /supplier — try AI market insights)"))
        for sup in suppliers.values():
            self.stdout.write(f"  username: {sup.user.username:<28} password: {DEMO_PASSWORD}   {sup.name} ({sup.county})")

        self.stdout.write(self.style.SUCCESS("\nFARMERS  (log in, then /farmer — try AI planting insights)"))
        for farmer in farmers.values():
            self.stdout.write(f"  username: {farmer.user.username:<28} password: {DEMO_PASSWORD}   {farmer.name} ({farmer.county}) — {farmer.crop_focus}")

        self.stdout.write(self.style.SUCCESS("\n" + line))
        self.stdout.write(self.style.WARNING(
            "Reminder: the AI engine needs a Groq API key configured under Admin panel → System settings "
            "(or a GROQ_API_KEY environment variable) before recommend/generate/insights/ask features will work.\n"
            "This same credentials list is also written to CHANGES.md. Run with --reset at any time to "
            "remove everything this command created (the admin account is left untouched)."
        ))
