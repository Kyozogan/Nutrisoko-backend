from django.db.models import Avg
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from institutions.models import Institution
from suppliers.models import Supplier
from farmers.models import Farmer
from menus.models import MenuPlan
from accounts.permissions import IsInstitution
from .models import County


class CountiesView(APIView):
    """All 47 Kenyan counties, for populating county dropdowns (registration, profile editing, etc)."""
    permission_classes = [AllowAny]

    def get(self, request):
        counties = County.objects.all().values("id", "name", "code")
        return Response(list(counties))


class PublicStatsView(APIView):
    """Headline numbers for the general/public landing page."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "institutions": Institution.objects.count(),
            "suppliers": Supplier.objects.count(),
            "farmers": Farmer.objects.count(),
            "menu_plans_generated": MenuPlan.objects.count(),
            "meals_planned": sum(mp.items.count() for mp in MenuPlan.objects.all()) if MenuPlan.objects.exists() else 0,
        })


class ComplianceReportView(APIView):
    """Nutrition-compliance summary across an institution's generated menu plans."""
    permission_classes = [IsInstitution]

    def get(self, request):
        institution = request.user.institution
        plans = MenuPlan.objects.filter(institution=institution, status__in=["approved", "ordered"])
        profile = getattr(institution, "dietary_profile", None)

        rows = []
        for plan in plans:
            summary = plan.nutrient_summary or {}
            rows.append({
                "week_start": plan.week_start,
                "avg_daily_calories": summary.get("avg_daily_calories"),
                "avg_daily_protein_g": summary.get("avg_daily_protein_g"),
                "total_cost": plan.total_cost,
                "meets_calorie_target": (
                    profile is not None and summary.get("avg_daily_calories") is not None
                    and abs(summary["avg_daily_calories"] - profile.target_calories) <= profile.target_calories * 0.1
                ),
            })

        return Response({
            "institution": institution.name,
            "target_calories": profile.target_calories if profile else None,
            "target_protein_g": profile.target_protein_g if profile else None,
            "weeks_reported": len(rows),
            "average_cost_per_week": round(sum(r["total_cost"] for r in rows) / len(rows), 2) if rows else 0,
            "rows": rows,
        })
