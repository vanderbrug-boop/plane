"""URL configuration for compliance/audit trail endpoints."""

from django.urls import path

from . import views

urlpatterns = [
    # Audit trail
    path(
        "workspaces/<uuid:workspace_id>/compliance/audit-log/",
        views.AuditLogListView.as_view(),
        name="audit-log-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/compliance/audit-log/record/<uuid:record_id>/",
        views.AuditLogRecordHistoryView.as_view(),
        name="audit-log-record-history",
    ),
    path(
        "workspaces/<uuid:workspace_id>/compliance/audit-log/integrity-check/",
        views.AuditIntegrityCheckView.as_view(),
        name="audit-integrity-check",
    ),
    # GDPR Data Processing Agreements
    path(
        "workspaces/<uuid:workspace_id>/compliance/dpas/",
        views.DataProcessingAgreementListCreateView.as_view(),
        name="dpa-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/compliance/dpas/<uuid:pk>/",
        views.DataProcessingAgreementDetailView.as_view(),
        name="dpa-detail",
    ),
]
