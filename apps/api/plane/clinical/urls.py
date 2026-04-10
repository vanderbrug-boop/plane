"""URL configuration for clinical trial management endpoints."""

from django.urls import path

from . import views

urlpatterns = [
    # Submissions (IND / CTA)
    path(
        "workspaces/<uuid:workspace_id>/clinical/submissions/",
        views.SubmissionListCreateView.as_view(),
        name="submission-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/submissions/<uuid:pk>/",
        views.SubmissionDetailView.as_view(),
        name="submission-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/submission-sections/<uuid:pk>/",
        views.SubmissionSectionUpdateView.as_view(),
        name="submission-section-update",
    ),

    # CROs
    path(
        "workspaces/<uuid:workspace_id>/clinical/cros/",
        views.CROListCreateView.as_view(),
        name="cro-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/cros/<uuid:pk>/",
        views.CRODetailView.as_view(),
        name="cro-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/cro-deliverables/",
        views.CRODeliverableListCreateView.as_view(),
        name="cro-deliverable-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/cro-kpis/",
        views.CROKpiListCreateView.as_view(),
        name="cro-kpi-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/cro-dashboard/",
        views.CRODashboardView.as_view(),
        name="cro-dashboard",
    ),

    # Clinical Trials
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/",
        views.ClinicalTrialListCreateView.as_view(),
        name="trial-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:pk>/",
        views.ClinicalTrialDetailView.as_view(),
        name="trial-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/sites/",
        views.TrialSiteListCreateView.as_view(),
        name="trial-site-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/sites/<uuid:pk>/",
        views.TrialSiteDetailView.as_view(),
        name="trial-site-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/enrollment/",
        views.EnrollmentDashboardView.as_view(),
        name="enrollment-dashboard",
    ),

    # TMF Documents
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/tmf/",
        views.TMFDocumentListCreateView.as_view(),
        name="tmf-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/tmf/<uuid:pk>/",
        views.TMFDocumentDetailView.as_view(),
        name="tmf-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/clinical/trials/<uuid:trial_id>/tmf-readiness/",
        views.TMFReadinessView.as_view(),
        name="tmf-readiness",
    ),
]
