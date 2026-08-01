from django.db import models


class MenuPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        ORDERED = "ordered", "Ordered"

    class Source(models.TextChoices):
        HEURISTIC = "heuristic", "Automatic (heuristic engine)"
        AI_AUTO = "ai_auto", "AI-recommended products"
        AI_MANUAL = "ai_manual", "AI menu from manually chosen products"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.CASCADE, related_name="menu_plans")
    week_start = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.HEURISTIC)
    duplicated_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicates",
        help_text="Set when this plan was created by reusing another week's menu rather than generated fresh — "
                   "e.g. repeating the same weekly rotation across a termly billing cycle.",
    )
    selected_ingredient_ids = models.JSONField(default=list, blank=True, help_text="Ingredient IDs the menu was constrained to build from (AI/manual flows).")
    ai_summary = models.TextField(blank=True, help_text="Natural-language summary returned by the AI when this plan was generated.")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nutrient_summary = models.JSONField(default=dict, blank=True)
    generation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = ("institution", "week_start")

    def __str__(self):
        return f"{self.institution.name} — week of {self.week_start}"


class MenuItem(models.Model):
    DAY_CHOICES = [(i, d) for i, d in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    )]

    menu_plan = models.ForeignKey(MenuPlan, on_delete=models.CASCADE, related_name="items")
    day = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    meal_slot = models.CharField(max_length=20)
    recipe = models.ForeignKey("nutrition.Recipe", on_delete=models.CASCADE, related_name="menu_items")
    servings = models.PositiveIntegerField(default=1)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["day", "meal_slot"]

    def __str__(self):
        return f"{self.get_day_display()} {self.meal_slot}: {self.recipe.name}"
