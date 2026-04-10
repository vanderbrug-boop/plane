"""URL configuration for AI service endpoints."""

from django.urls import path

from . import views

urlpatterns = [
    # AI Configuration
    path(
        "workspaces/<uuid:workspace_id>/ai/config/",
        views.AIConfigView.as_view(),
        name="ai-config",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/usage/",
        views.AIUsageView.as_view(),
        name="ai-usage",
    ),

    # Clinical Intelligence
    path(
        "workspaces/<uuid:workspace_id>/ai/query/",
        views.NaturalLanguageQueryView.as_view(),
        name="ai-nl-query",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/enrollment-forecast/",
        views.EnrollmentForecastView.as_view(),
        name="ai-enrollment-forecast",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/cro-scorecard/",
        views.CROScorecardView.as_view(),
        name="ai-cro-scorecard",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/regulatory-analysis/",
        views.RegulatoryAnalysisView.as_view(),
        name="ai-regulatory-analysis",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/status-report/",
        views.StatusReportView.as_view(),
        name="ai-status-report",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/meeting-summary/",
        views.MeetingSummaryView.as_view(),
        name="ai-meeting-summary",
    ),

    # Meetings & Reports
    path(
        "workspaces/<uuid:workspace_id>/ai/meetings/",
        views.MeetingListView.as_view(),
        name="ai-meetings-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/meetings/<uuid:pk>/",
        views.MeetingDetailView.as_view(),
        name="ai-meeting-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/reports/",
        views.ReportListView.as_view(),
        name="ai-reports-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ai/reports/<uuid:pk>/",
        views.ReportDetailView.as_view(),
        name="ai-report-detail",
    ),
]
