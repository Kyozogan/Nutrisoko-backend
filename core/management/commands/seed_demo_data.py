from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from institutions.models import Institution, DietaryProfile
from suppliers.models import Supplier, SupplierListing
from farmers.models import Farmer
from nutrition.models import Ingredient, Recipe, RecipeIngredient


class Command(BaseCommand):
    help = "Seed the database with demo institutions, suppliers, farmers, ingredients, and recipes."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username="admin").exists():
            self.stdout.write(self.style.WARNING("Demo data already present — skipping."))
            return

        User.objects.create_superuser(username="admin", email="admin@sokopulse.app", password="admin12345", role="admin")

        # ---- Ingredients ----
        ingredients_data = [
            ("Maize flour", "kg", Ingredient.Category.GRAIN, 3650, 90, 730, 40, 90, False, False, True),
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
            ("Cooking oil", "l", Ingredient.Category.FAT, 8840, 0, 0, 1000, 300, False, False, False),
            ("Bananas", "kg", Ingredient.Category.FRUIT, 890, 10, 230, 3, 100, False, False, False),
            ("Sweet potatoes", "kg", Ingredient.Category.GRAIN, 860, 20, 200, 1, 80, False, False, False),
            ("Spinach", "kg", Ingredient.Category.VEGETABLE, 230, 30, 40, 4, 60, False, False, False),
            ("Groundnuts", "kg", Ingredient.Category.LEGUME, 5670, 260, 160, 490, 250, False, False, False),
            ("Bread", "loaf", Ingredient.Category.GRAIN, 1060, 36, 196, 12, 70, False, False, True),
        ]
        ingredients = {}
        for (name, unit, cat, cal, prot, carb, fat, price, meat, dairy, gluten) in ingredients_data:
            ing = Ingredient.objects.create(
                name=name, unit=unit, category=cat, calories_per_unit=cal, protein_g_per_unit=prot,
                carbs_g_per_unit=carb, fat_g_per_unit=fat, default_price_per_unit=price,
                contains_meat=meat, contains_dairy=dairy, contains_gluten=gluten,
            )
            ingredients[name] = ing

        # ---- Recipes ----
        recipes_data = [
            ("Uji porridge with bananas", Recipe.MealType.BREAKFAST, [("Maize flour", 0.08), ("Milk", 0.15), ("Bananas", 0.12)]),
            ("Bread, eggs & milk", Recipe.MealType.BREAKFAST, [("Bread", 0.25), ("Eggs", 0.17), ("Milk", 0.2)]),
            ("Sweet potato & groundnut breakfast", Recipe.MealType.BREAKFAST, [("Sweet potatoes", 0.25), ("Groundnuts", 0.03)]),
            ("Ugali, beans & sukuma wiki", Recipe.MealType.LUNCH, [("Maize flour", 0.15), ("Beans", 0.12), ("Kale (Sukuma wiki)", 0.1), ("Cooking oil", 0.01), ("Onions", 0.02), ("Tomatoes", 0.03)]),
            ("Rice & chicken stew", Recipe.MealType.LUNCH, [("Rice", 0.15), ("Chicken", 0.12), ("Tomatoes", 0.05), ("Onions", 0.03), ("Cooking oil", 0.01), ("Carrots", 0.04)]),
            ("Beef & cabbage stew with ugali", Recipe.MealType.DINNER, [("Maize flour", 0.15), ("Beef", 0.1), ("Cabbage", 0.12), ("Onions", 0.02), ("Tomatoes", 0.04), ("Cooking oil", 0.01)]),
            ("Rice, beans & spinach", Recipe.MealType.DINNER, [("Rice", 0.14), ("Beans", 0.12), ("Spinach", 0.1), ("Onions", 0.02), ("Cooking oil", 0.01)]),
            ("Vegetable & egg stew with ugali", Recipe.MealType.DINNER, [("Maize flour", 0.14), ("Eggs", 0.08), ("Carrots", 0.05), ("Cabbage", 0.08), ("Cooking oil", 0.01)]),
            ("Banana & groundnut snack", Recipe.MealType.SNACK, [("Bananas", 0.1), ("Groundnuts", 0.03)]),
        ]
        for name, meal_type, ing_list in recipes_data:
            recipe = Recipe.objects.create(name=name, meal_type=meal_type, portion_size="1 plate", description=f"{name} — a balanced {meal_type} option built from locally available produce.")
            for ing_name, qty in ing_list:
                RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredients[ing_name], quantity_per_portion=Decimal(str(qty)))

        # ---- Institutions ----
        inst_user = User.objects.create_user(username="greenvalley_school", email="admin@greenvalley.ac.ke", password="demo12345", role="institution", county="Kiambu", phone="+254700111222")
        institution = Institution.objects.create(user=inst_user, name="Green Valley Primary School", type=Institution.Type.SCHOOL, county="Kiambu", headcount=420, budget_per_meal=Decimal("65.00"), contact_phone="+254700111222")
        DietaryProfile.objects.create(institution=institution, target_calories=1800, target_protein_g=45, target_carbs_g=250, target_fat_g=55, guideline_reference="Kenya School Meals Programme Guidelines")

        inst_user2 = User.objects.create_user(username="hopewell_hospital", email="nutrition@hopewell.or.ke", password="demo12345", role="institution", county="Nairobi", phone="+254700333444")
        institution2 = Institution.objects.create(user=inst_user2, name="Hopewell County Hospital", type=Institution.Type.HOSPITAL, county="Nairobi", headcount=180, budget_per_meal=Decimal("110.00"), contact_phone="+254700333444")
        DietaryProfile.objects.create(institution=institution2, target_calories=2100, target_protein_g=60, target_carbs_g=260, target_fat_g=65, restrictions=["dairy-free"], guideline_reference="Ministry of Health Patient Nutrition Guidelines")

        # ---- Suppliers ----
        sup_user = User.objects.create_user(username="kiambu_fresh_growers", email="sales@kiambufresh.co.ke", password="demo12345", role="supplier", county="Kiambu", phone="+254711222333")
        supplier = Supplier.objects.create(user=sup_user, name="Kiambu Fresh Growers Cooperative", county="Kiambu", contact_phone="+254711222333", verified=True)

        sup_user2 = User.objects.create_user(username="nairobi_grain_traders", email="orders@nairobigrain.co.ke", password="demo12345", role="supplier", county="Nairobi", phone="+254711444555")
        supplier2 = Supplier.objects.create(user=sup_user2, name="Nairobi Grain & Protein Traders", county="Nairobi", contact_phone="+254711444555", verified=True)

        listings = [
            (supplier, "Kale (Sukuma wiki)", 35), (supplier, "Cabbage", 30), (supplier, "Tomatoes", 75),
            (supplier, "Onions", 85), (supplier, "Carrots", 65), (supplier, "Bananas", 95),
            (supplier, "Sweet potatoes", 75), (supplier, "Spinach", 55),
            (supplier2, "Maize flour", 85), (supplier2, "Rice", 135), (supplier2, "Beans", 155),
            (supplier2, "Chicken", 430), (supplier2, "Beef", 530), (supplier2, "Eggs", 340),
            (supplier2, "Cooking oil", 290), (supplier2, "Milk", 65), (supplier2, "Groundnuts", 240),
            (supplier2, "Bread", 65),
        ]
        for sup, ing_name, price in listings:
            SupplierListing.objects.create(
                supplier=sup, ingredient=ingredients[ing_name], price_per_unit=Decimal(str(price)),
                quantity_available=Decimal("500"), available_from=date.today(), available_to=date.today() + timedelta(days=180),
            )

        # ---- Farmers ----
        f_user = User.objects.create_user(username="john_mwangi_farm", email="john@farm.co.ke", password="demo12345", role="farmer", county="Kiambu", phone="+254722555666")
        Farmer.objects.create(user=f_user, name="John Mwangi", county="Kiambu", crop_focus="Kale, Cabbage, Tomatoes", contact_phone="+254722555666")

        f_user2 = User.objects.create_user(username="mary_wanjiru_farm", email="mary@farm.co.ke", password="demo12345", role="farmer", county="Nairobi", phone="+254722777888")
        Farmer.objects.create(user=f_user2, name="Mary Wanjiru", county="Nairobi", crop_focus="Beans, Maize", contact_phone="+254722777888")

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded.\n"
            "  Admin       -> admin / admin12345\n"
            "  Institution -> greenvalley_school / demo12345\n"
            "  Institution -> hopewell_hospital / demo12345\n"
            "  Supplier    -> kiambu_fresh_growers / demo12345\n"
            "  Supplier    -> nairobi_grain_traders / demo12345\n"
            "  Farmer      -> john_mwangi_farm / demo12345\n"
            "  Farmer      -> mary_wanjiru_farm / demo12345\n"
        ))
