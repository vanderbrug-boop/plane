"""
API views for audit trail and compliance management.

These endpoints allow users to:
- Browse the audit log (read-only, filterable)
- Verify audit log integrity (hash chain validation)
- Manage Data Processing Agreements (GDPR)
"""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, DataProcessingAgreement
from .serializers import (
    AuditLogSerializer,
    DataProcessingAgreementSerializer,
)


class AuditLogListView(generics.ListAPIView):
    """
    Browse the audit trail. Read-only, filterable by model, user, date range, action.
    Per 21 CFR Part 11: audit logs must be available for independent review.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        workspace_id = self.kwargs.get("workspace_id")
        queryset = AuditLog.objects.filter(workspace_id=workspace_id)

        # Filters
        model_name = self.request.query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        record_id = self.request.query_params.get("record_id")
        if record_id:
            queryset = queryset.filter(record_id=record_id)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        return queryset.select_related().prefetch_related("signatures")


class AuditLogRecordHistoryView(generics.ListAPIView):
    """
    View complete change history for a specific record.
    Shows every field change with old/new values and who made the change.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        record_id = self.kwargs.get("record_id")
        return (
            AuditLog.objects.filter(record_id=record_id)
            .prefetch_related("signatures")
            .order_by("created_at")
        )


class AuditIntegrityCheckView(APIView):
    """
    Verify the integrity of the audit trail hash chain.
    Detects any tampered or missing records.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        logs = AuditLog.objects.filter(workspace_id=workspace_id).order_by("created_at")

        total = 0
        tampered = []

        for log in logs.iterator():
            total += 1
            if not log.verify_integrity():
                tampered.append(
                    {
                        "id": str(log.id),
                        "created_at": log.created_at.isoformat(),
                        "model_name": log.model_name,
                        "action": log.action,
                    }
                )

        return Response(
            {
                "total_records": total,
                "tampered_records": len(tampered),
                "integrity_valid": len(tampered) == 0,
                "tampered_details": tampered[:100],  # Cap at 100 for response size
            }
        )


class DataProcessingAgreementListCreateView(generics.ListCreateAPIView):
    """List and create Data Processing Agreements (GDPR compliance)."""

    serializer_class = DataProcessingAgreementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        workspace_id = self.kwargs.get("workspace_id")
        return DataProcessingAgreement.objects.filter(workspace_id=workspace_id)

    def perform_create(self, serializer):
        serializer.save(workspace_id=self.kwargs.get("workspace_id"))


class DataProcessingAgreementDetailView(generics.RetrieveUpdateAPIView):
    """View and update a specific DPA."""

    serializer_class = DataProcessingAgreementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        workspace_id = self.kwargs.get("workspace_id")
        return DataProcessingAgreement.objects.filter(workspace_id=workspace_id)
