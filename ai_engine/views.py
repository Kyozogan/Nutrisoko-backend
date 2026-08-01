from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from accounts.permissions import IsInstitution, IsSupplier, IsFarmer
from billing.gating import subscription_gate
from menus.serializers import MenuPlanSerializer
from . import groq_client as groq
from . import services

GENERIC_AI_ERROR = "The AI service is temporarily unavailable. Please try again shortly."


def ai_error_response(exc: Exception) -> Response:
    """
    Turn an AI-layer failure into a proper error response.

    In development (DEBUG=True) the real exception is surfaced so it's clear
    exactly what went wrong (missing key, bad request, network error, etc).
    In production, a generic message is returned instead — no fallback result
    is ever substituted.
    """
    if settings.DEBUG:
        detail = f"{exc.__class__.__name__}: {exc}"
    else:
        detail = GENERIC_AI_ERROR
    return Response({"detail": detail}, status=503)


class RecommendIngredientsView(APIView):
    permission_classes = [IsInstitution]

    def post(self, request):
        gate = subscription_gate(request)
        if gate:
            return gate
        institution = request.user.institution
        if not hasattr(institution, "dietary_profile"):
            return Response({"detail": "Set up a dietary profile before requesting recommendations."}, status=400)
        budget_override = request.data.get("budget_override")
        try:
            result = services.recommend_ingredients(institution, budget_override=budget_override)
        except groq.GroqUnavailable as exc:
            return ai_error_response(exc)
        return Response(result)


class GenerateAIMenuView(APIView):
    permission_classes = [IsInstitution]

    def post(self, request):
        gate = subscription_gate(request)
        if gate:
            return gate
        institution = request.user.institution
        ingredient_ids = request.data.get("ingredient_ids") or []
        week_start = request.data.get("week_start")
        mode = request.data.get("mode", "ai_manual")  # "ai_auto" | "ai_manual"
        if not ingredient_ids or not week_start:
            return Response({"detail": "ingredient_ids and week_start are required."}, status=400)
        try:
            plan = services.generate_ai_weekly_menu(institution, ingredient_ids, week_start, mode)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except groq.GroqUnavailable as exc:
            return ai_error_response(exc)
        return Response(MenuPlanSerializer(plan).data, status=201)


class SupplierInsightsView(APIView):
    permission_classes = [IsSupplier]

    def get(self, request):
        gate = subscription_gate(request)
        if gate:
            return gate
        try:
            result = services.build_supplier_insights(request.user.supplier)
        except groq.GroqUnavailable as exc:
            return ai_error_response(exc)
        return Response(result)


class FarmerInsightsView(APIView):
    permission_classes = [IsFarmer]

    def get(self, request):
        gate = subscription_gate(request)
        if gate:
            return gate
        try:
            result = services.build_farmer_insights(request.user.farmer)
        except groq.GroqUnavailable as exc:
            return ai_error_response(exc)
        return Response(result)


class AskAssistantView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        gate = subscription_gate(request)
        if gate:
            return gate
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response({"detail": "question is required."}, status=400)
        try:
            result = services.answer_question(request.user, question)
        except groq.GroqUnavailable as exc:
            return ai_error_response(exc)
        return Response(result)
