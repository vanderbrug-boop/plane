"""
Audit trail middleware that automatically captures all data changes.

This middleware hooks into Django's model save/delete signals to create
immutable AuditLog records for every data modification. It also captures
the requesting user's IP address and identity from the HTTP request.

Per 21 CFR Part 11: timestamps are computer-generated and cannot be
manually overridden. The hash chain ensures chronological integrity.
"""

import threading

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.utils import timezone

_thread_local = threading.local()

# Models that are themselves audit infrastructure (don't audit recursively)
EXCLUDED_MODELS = {
    "AuditLog",
    "ElectronicSignature",
    "AccessControlLog",
    "AIUsageLog",
}


def get_current_request_context():
    """Retrieve the current request context set by the middleware."""
    return getattr(_thread_local, "audit_context", None)


class AuditMiddleware:
    """
    Django middleware that:
    1. Stores request context (user, IP) in thread-local for signal handlers
    2. Connects model signals on first request
    """

    _signals_connected = False

    def __init__(self, get_response):
        self.get_response = get_response
        if not AuditMiddleware._signals_connected:
            self._connect_signals()
            AuditMiddleware._signals_connected = True

    def __call__(self, request):
        # Store request context in thread-local for signal handlers
        _thread_local.audit_context = {
            "user_id": getattr(request.user, "id", None) if hasattr(request, "user") else None,
            "user_email": getattr(request.user, "email", "") if hasattr(request, "user") else "",
            "user_display_name": (
                getattr(request.user, "display_name", "")
                if hasattr(request, "user")
                else ""
            ),
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "workspace_id": self._get_workspace_id(request),
        }

        response = self.get_response(request)

        # Clean up thread-local
        _thread_local.audit_context = None
        return response

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @staticmethod
    def _get_workspace_id(request):
        """Extract workspace_id from URL path if present."""
        # Plane URLs typically include /workspaces/<slug>/ - extract if available
        if hasattr(request, "resolver_match") and request.resolver_match:
            kwargs = request.resolver_match.kwargs or {}
            return kwargs.get("workspace_id") or kwargs.get("slug")
        return None

    def _connect_signals(self):
        """Connect Django model signals for automatic audit logging."""
        pre_save.connect(self._pre_save_handler)
        post_save.connect(self._post_save_handler)
        pre_delete.connect(self._pre_delete_handler)

    @staticmethod
    def _pre_save_handler(sender, instance, **kwargs):
        """Capture old values before save for change tracking."""
        model_name = sender.__name__
        if model_name in EXCLUDED_MODELS:
            return

        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._audit_old_values = {
                    field.name: str(getattr(old_instance, field.name, ""))
                    for field in sender._meta.fields
                }
                instance._audit_is_update = True
            except sender.DoesNotExist:
                instance._audit_is_update = False
        else:
            instance._audit_is_update = False

    @staticmethod
    def _post_save_handler(sender, instance, created, **kwargs):
        """Create audit log entries after save."""
        from .models import AuditLog

        model_name = sender.__name__
        if model_name in EXCLUDED_MODELS:
            return

        context = get_current_request_context() or {}
        action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE

        if created:
            # Log the creation with all field values
            AuditLog.objects.create(
                workspace_id=context.get("workspace_id") or getattr(instance, "workspace_id", None),
                user_id=context.get("user_id"),
                user_email=context.get("user_email", ""),
                user_display_name=context.get("user_display_name", ""),
                action=action,
                model_name=model_name,
                record_id=instance.pk,
                field_name="*",
                old_value="",
                new_value=f"Record created: {instance.pk}",
                ip_address=context.get("ip_address"),
                user_agent=context.get("user_agent", ""),
            )
        else:
            # Log each changed field individually
            old_values = getattr(instance, "_audit_old_values", {})
            for field in sender._meta.fields:
                new_val = str(getattr(instance, field.name, ""))
                old_val = old_values.get(field.name, "")
                if new_val != old_val:
                    AuditLog.objects.create(
                        workspace_id=(
                            context.get("workspace_id")
                            or getattr(instance, "workspace_id", None)
                        ),
                        user_id=context.get("user_id"),
                        user_email=context.get("user_email", ""),
                        user_display_name=context.get("user_display_name", ""),
                        action=action,
                        model_name=model_name,
                        record_id=instance.pk,
                        field_name=field.name,
                        old_value=old_val,
                        new_value=new_val,
                        ip_address=context.get("ip_address"),
                        user_agent=context.get("user_agent", ""),
                    )

    @staticmethod
    def _pre_delete_handler(sender, instance, **kwargs):
        """Create audit log entry before deletion."""
        from .models import AuditLog

        model_name = sender.__name__
        if model_name in EXCLUDED_MODELS:
            return

        context = get_current_request_context() or {}

        AuditLog.objects.create(
            workspace_id=context.get("workspace_id") or getattr(instance, "workspace_id", None),
            user_id=context.get("user_id"),
            user_email=context.get("user_email", ""),
            user_display_name=context.get("user_display_name", ""),
            action=AuditLog.Action.DELETE,
            model_name=model_name,
            record_id=instance.pk,
            field_name="*",
            old_value=f"Record deleted: {instance.pk}",
            new_value="",
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent", ""),
        )
