from django.db import models


class Ingredient(models.Model):
    class Category(models.TextChoices):
        GRAIN = "grain", "Grain / Staple"
        VEGETABLE = "vegetable", "Vegetable"
        FRUIT = "fruit", "Fruit"
        PROTEIN = "protein", "Protein"
        DAIRY = "dairy", "Dairy"
        LEGUME = "legume", "Legume"
        FAT = "fat", "Fat / Oil"
        OTHER = "other", "Other"

    name = models.CharField(max_length=150, unique=True)
    unit = models.CharField(max_length=20, default="kg")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    calories_per_unit = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    protein_g_per_unit = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    carbs_g_per_unit = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fat_g_per_unit = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    default_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contains_meat = models.BooleanField(default=False)
    contains_dairy = models.BooleanField(default=False)
    contains_gluten = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        DINNER = "dinner", "Dinner"
        SNACK = "snack", "Snack"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    portion_size = models.CharField(max_length=100, blank=True, help_text="e.g. 1 plate, 350g")
    prep_notes = models.TextField(blank=True)
    ingredients = models.ManyToManyField(Ingredient, through="RecipeIngredient", related_name="recipes")
    ai_generated = models.BooleanField(default=False, help_text="Created by the AI weekly-menu generator rather than the curated recipe library.")

    class Meta:
        ordering = ["meal_type", "name"]

    def __str__(self):
        return self.name

    @property
    def contains_meat(self):
        return self.recipeingredient_set.filter(ingredient__contains_meat=True).exists()

    @property
    def contains_dairy(self):
        return self.recipeingredient_set.filter(ingredient__contains_dairy=True).exists()

    @property
    def contains_gluten(self):
        return self.recipeingredient_set.filter(ingredient__contains_gluten=True).exists()


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_per_portion = models.DecimalField(max_digits=8, decimal_places=3)

    class Meta:
        unique_together = ("recipe", "ingredient")

    def __str__(self):
        return f"{self.ingredient.name} in {self.recipe.name}"
