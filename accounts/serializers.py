from django.db import transaction
from rest_framework import serializers

from .models import User
from institutions.models import Institution, DietaryProfile
from suppliers.models import Supplier
from farmers.models import Farmer


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    organisation_name = serializers.CharField(write_only=True)
    county = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # institution-only optional fields
    institution_type = serializers.ChoiceField(
        choices=Institution.Type.choices, required=False, default=Institution.Type.SCHOOL
    )
    headcount = serializers.IntegerField(required=False, default=0)
    billing_cycle = serializers.ChoiceField(choices=Institution.BillingCycle.choices, required=False, default=Institution.BillingCycle.WEEKLY)
    budget_mode = serializers.ChoiceField(choices=Institution.BudgetMode.choices, required=False, default=Institution.BudgetMode.PER_MEAL)
    budget_total_per_cycle = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, default=None)
    # Legacy single figure — still accepted for backward compatibility, but institutions
    # are now expected to fill in whichever of the three meal budgets below actually apply
    # (budget_mode="per_meal"), or budget_total_per_cycle instead (budget_mode="total_per_cycle").
    budget_per_meal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    budget_breakfast = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    budget_lunch = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    budget_supper = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)

    # farmer-only optional field
    crop_focus = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "username", "email", "password", "role", "phone", "county",
            "organisation_name", "institution_type", "headcount",
            "billing_cycle", "budget_mode", "budget_total_per_cycle", "budget_per_meal",
            "budget_breakfast", "budget_lunch", "budget_supper", "crop_focus",
        ]

    def validate_role(self, value):
        if value not in (User.Role.INSTITUTION, User.Role.SUPPLIER, User.Role.FARMER):
            raise serializers.ValidationError("Self-registration is only available for institutions, suppliers, and farmers.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        org_name = validated_data.pop("organisation_name")
        institution_type = validated_data.pop("institution_type", Institution.Type.SCHOOL)
        headcount = validated_data.pop("headcount", 0)
        billing_cycle = validated_data.pop("billing_cycle", Institution.BillingCycle.WEEKLY)
        budget_mode = validated_data.pop("budget_mode", Institution.BudgetMode.PER_MEAL)
        budget_total_per_cycle = validated_data.pop("budget_total_per_cycle", None)
        budget_per_meal = validated_data.pop("budget_per_meal", 0)
        budget_breakfast = validated_data.pop("budget_breakfast", None)
        budget_lunch = validated_data.pop("budget_lunch", None)
        budget_supper = validated_data.pop("budget_supper", None)
        crop_focus = validated_data.pop("crop_focus", "")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        if user.role == User.Role.INSTITUTION:
            inst = Institution(
                user=user, name=org_name, type=institution_type,
                county=user.county, headcount=headcount,
                billing_cycle=billing_cycle, budget_mode=budget_mode, budget_total_per_cycle=budget_total_per_cycle,
                budget_per_meal=budget_per_meal,
                budget_breakfast=budget_breakfast, budget_lunch=budget_lunch, budget_supper=budget_supper,
                contact_phone=user.phone,
            )
            # In total_per_cycle mode, or when at least one specific meal budget was filled in,
            # that's the source of truth — budget_per_meal is derived from it, not the other way round.
            if budget_mode == Institution.BudgetMode.TOTAL_PER_CYCLE or inst.meal_budgets_set():
                inst.recompute_budget_per_meal()
            inst.save()
            DietaryProfile.objects.create(institution=inst)
        elif user.role == User.Role.SUPPLIER:
            Supplier.objects.create(user=user, name=org_name, county=user.county, contact_phone=user.phone)
        elif user.role == User.Role.FARMER:
            Farmer.objects.create(user=user, name=org_name, county=user.county, crop_focus=crop_focus, contact_phone=user.phone)

        return user


class MeSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "phone", "county", "profile"]

    def get_profile(self, obj):
        if obj.role == User.Role.INSTITUTION and hasattr(obj, "institution"):
            return {"id": obj.institution.id, "name": obj.institution.name, "type": obj.institution.type}
        if obj.role == User.Role.SUPPLIER and hasattr(obj, "supplier"):
            return {"id": obj.supplier.id, "name": obj.supplier.name, "verified": obj.supplier.verified}
        if obj.role == User.Role.FARMER and hasattr(obj, "farmer"):
            return {"id": obj.farmer.id, "name": obj.farmer.name, "crop_focus": obj.farmer.crop_focus}
        return None
