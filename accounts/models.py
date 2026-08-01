from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class AdminAwareUserManager(UserManager):
    """
    Identical to Django's default UserManager, except `createsuperuser`
    (and any direct create_superuser() call) sets role="admin" unless one
    was explicitly passed in. Without this, a superuser created the normal
    Django way ends up with role="" — able to log in, but redirected away
    from /admin-panel because it doesn't match the "admin" role check.
    """
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        INSTITUTION = "institution", "Institution"
        SUPPLIER = "supplier", "Supplier"
        FARMER = "farmer", "Farmer"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=32, blank=True)
    county = models.CharField(max_length=64, blank=True)
    email = models.EmailField(unique=True)

    objects = AdminAwareUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.role})"
