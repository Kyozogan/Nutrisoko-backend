"""
Small helper functions other apps call to raise in-app notifications. Kept
deliberately dependency-light (no signals/celery) so a notification is
created synchronously, in the same transaction as the event that caused it —
if the order/menu save rolls back, so does the notification.
"""
from .models import Notification


def notify(recipient, title, message="", *, notification_type=Notification.NotificationType.SYSTEM,
           level=Notification.Level.INFO, related_order=None, link=""):
    """Create a single notification. `recipient` may be None, in which case this is a no-op
    (keeps call sites simple when e.g. an institution has no linked user yet)."""
    if recipient is None:
        return None
    return Notification.objects.create(
        recipient=recipient, title=title, message=message,
        notification_type=notification_type, level=level,
        related_order=related_order, link=link,
    )


def notify_many(recipients, title, message="", **kwargs):
    """Create the same notification for a list/queryset of users."""
    return [notify(r, title, message, **kwargs) for r in recipients if r is not None]
