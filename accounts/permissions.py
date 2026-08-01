from rest_framework.permissions import BasePermission


class IsRole(BasePermission):
    """Generic role-check permission factory usage: IsRole('institution')"""
    allowed_role = None

    def __init__(self, allowed_role=None):
        if allowed_role:
            self.allowed_role = allowed_role

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == self.allowed_role or request.user.role == "admin" or request.user.is_superuser)
        )


class IsInstitution(IsRole):
    allowed_role = "institution"


class IsSupplier(IsRole):
    allowed_role = "supplier"


class IsFarmer(IsRole):
    allowed_role = "farmer"


class IsAdminRole(IsRole):
    allowed_role = "admin"
