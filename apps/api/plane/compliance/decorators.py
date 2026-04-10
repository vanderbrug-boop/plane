"""
Decorators for compliance-aware views.

@audit_logged — Adds explicit audit context to a view action
@requires_esignature — Requires electronic signature (password re-entry)
                       before allowing the action to proceed
"""

import functools

from django.http import JsonResponse
from django.utils import timezone

from .models import AuditLog, ElectronicSignature


def audit_logged(action, model_name, reason_required=False):
    """
    Decorator for views that need explicit audit logging beyond
    the automatic model-level tracking.

    Usage:
        @audit_logged(action="approve", model_name="Submission", reason_required=True)
        def approve_submission(request, submission_id):
            ...
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if reason_required:
                reason = request.data.get("reason", "") if hasattr(request, "data") else ""
                if not reason:
                    return JsonResponse(
                        {"error": "A reason is required for this action (regulatory compliance)."},
                        status=400,
                    )

            response = view_func(request, *args, **kwargs)

            # Log the action after successful execution
            if hasattr(response, "status_code") and 200 <= response.status_code < 300:
                record_id = kwargs.get("pk") or kwargs.get("id") or kwargs.get("submission_id")
                AuditLog.objects.create(
                    workspace_id=kwargs.get("workspace_id") or kwargs.get("slug"),
                    user_id=getattr(request.user, "id", None),
                    user_email=getattr(request.user, "email", ""),
                    action=action,
                    model_name=model_name,
                    record_id=record_id,
                    reason=request.data.get("reason", "") if hasattr(request, "data") else "",
                    ip_address=_get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )

            return response

        return wrapper

    return decorator


def requires_esignature(meaning, model_name):
    """
    Decorator that requires electronic signature (password re-entry)
    before allowing the action. Per 21 CFR Part 11 Subpart C.

    The request must include:
    - esignature_password: The user's password for re-authentication
    - esignature_meaning: Must match the expected meaning

    Usage:
        @requires_esignature(meaning="approved", model_name="CRODeliverable")
        def approve_deliverable(request, deliverable_id):
            ...
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            data = request.data if hasattr(request, "data") else {}

            password = data.get("esignature_password")
            sig_meaning = data.get("esignature_meaning")

            if not password:
                return JsonResponse(
                    {
                        "error": "Electronic signature required. Please re-enter your password.",
                        "requires_esignature": True,
                        "expected_meaning": meaning,
                    },
                    status=403,
                )

            if sig_meaning != meaning:
                return JsonResponse(
                    {
                        "error": f"Signature meaning must be '{meaning}'.",
                        "requires_esignature": True,
                        "expected_meaning": meaning,
                    },
                    status=400,
                )

            # Verify password (re-authentication)
            user = request.user
            if not user.check_password(password):
                return JsonResponse(
                    {"error": "Invalid password. Electronic signature failed."},
                    status=403,
                )

            # Execute the view
            response = view_func(request, *args, **kwargs)

            # Record the electronic signature if action succeeded
            if hasattr(response, "status_code") and 200 <= response.status_code < 300:
                record_id = kwargs.get("pk") or kwargs.get("id")
                audit_entry = AuditLog.objects.create(
                    workspace_id=kwargs.get("workspace_id") or kwargs.get("slug"),
                    user_id=user.id,
                    user_email=user.email,
                    action=AuditLog.Action.SIGN,
                    model_name=model_name,
                    record_id=record_id,
                    reason=data.get("reason", ""),
                    ip_address=_get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )

                ElectronicSignature.objects.create(
                    audit_log=audit_entry,
                    user_id=user.id,
                    user_email=user.email,
                    meaning=meaning,
                )

            return response

        return wrapper

    return decorator


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
