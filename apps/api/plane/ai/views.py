"""
API views for AI-powered clinical trial features.

All endpoints are workspace-scoped and require authentication.
AI interactions are audit-logged per 21 CFR Part 11.
"""

import logging

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIReport, AIUsageLog, AIWorkspaceConfig, ScheduledMeeting
from .serializers import (
    AIReportListSerializer,
    AIReportSerializer,
    AIUsageLogSerializer,
    AIWorkspaceConfigSerializer,
    AIWorkspaceConfigUpdateSerializer,
    CROScorecardSerializer,
    EnrollmentForecastSerializer,
    MeetingSummarySerializer,
    NLQuerySerializer,
    RegulatoryAnalysisSerializer,
    ScheduledMeetingSerializer,
    StatusReportSerializer,
)
from .services.clinical_intelligence import ClinicalIntelligenceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI Configuration
# ---------------------------------------------------------------------------

class AIConfigView(APIView):
    """Get or update workspace AI configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        config, _ = AIWorkspaceConfig.objects.get_or_create(workspace_id=workspace_id)
        return Response(AIWorkspaceConfigSerializer(config).data)

    def patch(self, request, workspace_id):
        config, _ = AIWorkspaceConfig.objects.get_or_create(workspace_id=workspace_id)
        serializer = AIWorkspaceConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "provider" in data:
            config.provider = data["provider"]
        if "model" in data:
            config.model = data["model"]
        if "api_key" in data:
            config.api_key_encrypted = data["api_key"]  # In prod: encrypt with Fernet
        if "recall_api_key" in data:
            config.recall_api_key_encrypted = data["recall_api_key"]
        if "monthly_token_budget" in data:
            config.monthly_token_budget = data["monthly_token_budget"]
        if "features_enabled" in data:
            config.features_enabled = data["features_enabled"]
        if "auto_join_meetings" in data:
            config.auto_join_meetings = data["auto_join_meetings"]

        config.save()
        return Response(AIWorkspaceConfigSerializer(config).data)


class AIUsageView(generics.ListAPIView):
    """View AI usage logs for a workspace."""

    serializer_class = AIUsageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AIUsageLog.objects.filter(workspace_id=self.kwargs["workspace_id"])
        feature = self.request.query_params.get("feature")
        if feature:
            qs = qs.filter(feature=feature)
        return qs[:100]


# ---------------------------------------------------------------------------
# Clinical Intelligence Endpoints
# ---------------------------------------------------------------------------

class NaturalLanguageQueryView(APIView):
    """
    Natural language query endpoint.
    Ask questions about your clinical trial data in plain English.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        serializer = NLQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        result = service.natural_language_query(serializer.validated_data["question"])
        return Response(result)


class EnrollmentForecastView(APIView):
    """Generate enrollment forecast for a clinical trial."""

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        serializer = EnrollmentForecastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        result = service.forecast_enrollment(str(serializer.validated_data["trial_id"]))
        return Response(result)


class CROScorecardView(APIView):
    """Generate AI-powered CRO performance scorecards."""

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        serializer = CROScorecardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        cro_id = serializer.validated_data.get("cro_id")
        result = service.generate_cro_scorecard(str(cro_id) if cro_id else None)
        return Response(result)


class RegulatoryAnalysisView(APIView):
    """Run regulatory gap analysis across all active submissions."""

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        result = service.regulatory_gap_analysis()
        return Response(result)


class StatusReportView(APIView):
    """Generate AI-powered status reports."""

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        serializer = StatusReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        result = service.generate_status_report(
            report_type=data["report_type"],
            trial_id=str(data["trial_id"]) if data.get("trial_id") else None,
            audience=data.get("audience", "team"),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class MeetingSummaryView(APIView):
    """Trigger meeting summarization for a completed meeting."""

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        serializer = MeetingSummarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ClinicalIntelligenceService(
            workspace_id=str(workspace_id),
            user_id=str(request.user.id) if hasattr(request.user, "id") else None,
        )

        result = service.summarize_meeting(str(serializer.validated_data["meeting_id"]))
        return Response(result)


# ---------------------------------------------------------------------------
# Meetings & Reports (CRUD)
# ---------------------------------------------------------------------------

class MeetingListView(generics.ListAPIView):
    """List meetings for a workspace."""

    serializer_class = ScheduledMeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ScheduledMeeting.objects.filter(workspace_id=self.kwargs["workspace_id"])
        meeting_type = self.request.query_params.get("type")
        if meeting_type:
            qs = qs.filter(meeting_type=meeting_type)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs[:50]


class MeetingDetailView(generics.RetrieveAPIView):
    """Get meeting details including summary and action items."""

    serializer_class = ScheduledMeetingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return ScheduledMeeting.objects.filter(workspace_id=self.kwargs["workspace_id"])


class ReportListView(generics.ListAPIView):
    """List AI-generated reports."""

    serializer_class = AIReportListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AIReport.objects.filter(workspace_id=self.kwargs["workspace_id"])
        report_type = self.request.query_params.get("type")
        if report_type:
            qs = qs.filter(report_type=report_type)
        return qs[:50]


class ReportDetailView(generics.RetrieveAPIView):
    """Get full report content."""

    serializer_class = AIReportSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return AIReport.objects.filter(workspace_id=self.kwargs["workspace_id"])
