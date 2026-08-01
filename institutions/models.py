from django.conf import settings
from django.db import models


class Institution(models.Model):
    class Type(models.TextChoices):
        SCHOOL = "school", "School"
        HOSPITAL = "hospital", "Hospital"
        CANTEEN = "canteen", "Canteen"

    class BillingCycle(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        TERMLY = "termly", "Termly (3 months)"

    # Approximate number of days in each billing cycle, used to convert a single
    # cycle-total budget figure into an equivalent per-meal budget for the menu engine.
    CYCLE_DAYS = {BillingCycle.WEEKLY: 7, BillingCycle.MONTHLY: 30, BillingCycle.TERMLY: 90}

    class BudgetMode(models.TextChoices):
        PER_MEAL = "per_meal", "Split by meal (breakfast / lunch / supper)"
        TOTAL_PER_CYCLE = "total_per_cycle", "One total amount for the whole billing cycle"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="institution")
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SCHOOL)
    county = models.CharField(max_length=64, blank=True)
    headcount = models.PositiveIntegerField(default=0)
    billing_cycle = models.CharField(
        max_length=20, choices=BillingCycle.choices, default=BillingCycle.WEEKLY,
        help_text="How often this institution charges/budgets for meals — e.g. a canteen billing "
                   "individuals monthly, or a boarding school charging per school term.",
    )
    budget_mode = models.CharField(
        max_length=20, choices=BudgetMode.choices, default=BudgetMode.PER_MEAL,
        help_text="Whether the budget below is split per meal (breakfast/lunch/supper) or given as "
                   "one total figure per person for the whole billing cycle.",
    )
    budget_total_per_cycle = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Only used when budget_mode is 'total_per_cycle': the total meal budget per "
                   "learner/patient/staff member for one whole billing cycle (e.g. per term, per month).",
    )
    budget_per_meal = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Overall fallback budget per meal (KSh). Auto-derived from the breakfast/lunch/supper "
                   "budgets, or from budget_total_per_cycle, depending on budget_mode; used by the menu "
                   "engine for any meal slot that doesn't have its own budget.",
    )
    budget_breakfast = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Budget per learner/patient for breakfast (KSh). Leave blank if this institution doesn't offer breakfast.",
    )
    budget_lunch = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Budget per learner/patient for lunch (KSh). Leave blank if this institution doesn't offer lunch.",
    )
    budget_supper = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Budget per learner/patient for supper (KSh). Leave blank if this institution doesn't offer supper.",
    )
    contact_phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def meal_budgets_set(self):
        """Dict of only the meal budgets that have actually been configured for this institution.
        Always empty in TOTAL_PER_CYCLE mode — that mode uses one blanket figure instead, so every
        meal slot is offered and priced from the derived budget_per_meal."""
        if self.budget_mode == self.BudgetMode.TOTAL_PER_CYCLE:
            return {}
        return {
            k: v for k, v in {
                "breakfast": self.budget_breakfast,
                "lunch": self.budget_lunch,
                "supper": self.budget_supper,
            }.items() if v is not None
        }

    def recompute_budget_per_meal(self):
        """Keeps the legacy `budget_per_meal` fallback in sync — either as the average of whichever
        per-meal budgets are set, or (in TOTAL_PER_CYCLE mode) as the cycle total divided evenly
        across every meal in the billing cycle — so older code paths (AI weekly-budget maths, the
        menu engine) keep working unchanged either way."""
        if self.budget_mode == self.BudgetMode.TOTAL_PER_CYCLE:
            if self.budget_total_per_cycle:
                cycle_days = self.CYCLE_DAYS.get(self.billing_cycle, 7)
                self.budget_per_meal = round(self.budget_total_per_cycle / (cycle_days * 3), 2)
            return
        set_budgets = list(self.meal_budgets_set().values())
        if set_budgets:
            self.budget_per_meal = sum(set_budgets) / len(set_budgets)


class Site(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.name} ({self.institution.name})"


class DietaryProfile(models.Model):
    institution = models.OneToOneField(Institution, on_delete=models.CASCADE, related_name="dietary_profile")
    restrictions = models.JSONField(default=list, blank=True)  # e.g. ["vegetarian", "no-pork"]
    target_calories = models.PositiveIntegerField(default=2000, help_text="kcal / person / day")
    target_protein_g = models.PositiveIntegerField(default=50)
    target_carbs_g = models.PositiveIntegerField(default=260)
    target_fat_g = models.PositiveIntegerField(default=65)
    guideline_reference = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Dietary profile — {self.institution.name}"
