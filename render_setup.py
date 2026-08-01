# render_setup.py
#
# Run on deploy (e.g. as Render's release/build command) to make sure a working admin
# superuser always exists, with credentials matching CHANGES.md and the
# seed_conference_demo command — see core/demo_credentials.py, the single source of
# truth for these values.
#
#   python render_setup.py
#
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sokopulse.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import User as UserModel  # Import the custom User model
from core.demo_credentials import ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD

User = get_user_model()

user, created = User.objects.get_or_create(
    username=ADMIN_USERNAME,
    defaults={'email': ADMIN_EMAIL, 'role': UserModel.Role.ADMIN},
)

# Always (re)apply password + admin flags, whether the account was just created or already
# existed. This matters: without it, an "admin" user left over from an earlier setup (with an
# unknown password) would silently keep its old password, and nobody would be able to log in
# with the documented credentials.
user.set_password(ADMIN_PASSWORD)
user.email = ADMIN_EMAIL
user.role = UserModel.Role.ADMIN
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.save()

if created:
    print(f'✅ Superuser "{ADMIN_USERNAME}" created with ADMIN role. Password: {ADMIN_PASSWORD}')
else:
    print(f'✅ Superuser "{ADMIN_USERNAME}" already existed — role/flags/password (re)applied. Password: {ADMIN_PASSWORD}')
