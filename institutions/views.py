from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsInstitution
from .models import Institution, Site, DietaryProfile
from .serializers import InstitutionSerializer, SiteSerializer, DietaryProfileSerializer


class MyInstitutionViewSet(viewsets.ViewSet):
    """A convenience viewset exposing the logged-in institution's own profile."""
    permission_classes = [IsInstitution]

    def list(self, request):
        inst = request.user.institution
        return Response(InstitutionSerializer(inst).data)

    def partial_update(self, request, pk=None):
        inst = request.user.institution
        serializer = InstitutionSerializer(inst, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["patch"])
    def dietary_profile(self, request):
        inst = request.user.institution
        profile, _ = DietaryProfile.objects.get_or_create(institution=inst)
        serializer = DietaryProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get", "post"])
    def sites(self, request):
        inst = request.user.institution
        if request.method == "GET":
            return Response(SiteSerializer(inst.sites.all(), many=True).data)
        serializer = SiteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(institution=inst)
        return Response(serializer.data, status=201)
