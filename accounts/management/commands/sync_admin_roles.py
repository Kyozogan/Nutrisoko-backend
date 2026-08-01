from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Sets role='admin' on any superuser account whose role isn't set correctly. "
        "Fixes accounts created with `createsuperuser` before this was handled automatically, "
        "and is safe to run any time — it only ever touches is_superuser=True accounts."
    )

    def handle(self, *args, **options):
        broken = User.objects.filter(is_superuser=True).exclude(role=User.Role.ADMIN)
        if not broken.exists():
            self.stdout.write(self.style.SUCCESS("All superuser accounts already have role='admin'. Nothing to do."))
            return
        for user in broken:
            old_role = user.role or "(empty)"
            user.role = User.Role.ADMIN
            user.save(update_fields=["role"])
            self.stdout.write(f"  Fixed {user.username}: role was {old_role!r}, now 'admin'")
        self.stdout.write(self.style.SUCCESS(f"Fixed {broken.count()} account(s)."))
