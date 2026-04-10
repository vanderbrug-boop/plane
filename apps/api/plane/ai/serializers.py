"""Serializers for AI service endpoints."""

from rest_framework import serializers

from .models import AIReport, AIUsageLog, AIWorkspaceConfig, ScheduledMeeting


class AIWorkspaceConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIWorkspaceConfig
        fields = [
            "id", "workspace_id", "provider", "model",
            "monthly_token_budget", "tokens_used_this_month", "budget_reset_date",
            "features_enabled", "auto_join_meetings",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "workspace_id", "tokens_used_this_month", "created_at", "updated_at"]

    # Never expose API keys in responses
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["api_key_configured"] = bool(instance.api_key_encrypted)
        data["recall_key_configured"] = bool(instance.recall_api_key_encrypted)
        return data


class AIWorkspaceConfigUpdateSerializer(serializers.Serializer):
    """For updating config including API keys."""
    provider = serializers.CharField(required=False)
    model = serializers.CharField(required=False)
    api_key = serializers.CharField(required=False, write_only=True)
    recall_api_key = serializers.CharField(required=False, write_only=True)
    monthly_token_budget = serializers.IntegerField(required=False)
    features_enabled = serializers.JSONField(required=False)
    auto_join_meetings = serializers.BooleanField(required=False)


class AIUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageLog
        fields = [
            "id", "workspace_id", "user_id", "feature", "model",
            "input_tokens", "output_tokens", "request_summary",
            "response_summary", "duration_ms", "created_at",
        ]
        read_only_fields = fields


class NLQuerySerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)


class EnrollmentForecastSerializer(serializers.Serializer):
    trial_id = serializers.UUIDField()


class CROScorecardSerializer(serializers.Serializer):
    cro_id = serializers.UUIDField(required=False)


class RegulatoryAnalysisSerializer(serializers.Serializer):
    pass  # No input needed — analyzes all active submissions


class StatusReportSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=[
        "trial_status", "cro_oversight", "regulatory_update",
        "executive_summary", "board_update",
    ])
    trial_id = serializers.UUIDField(required=False)
    audience = serializers.ChoiceField(
        choices=["team", "executive", "board", "investor", "regulatory", "cro"],
        default="team",
    )


class MeetingSummarySerializer(serializers.Serializer):
    meeting_id = serializers.UUIDField()


class ScheduledMeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledMeeting
        fields = [
            "id", "workspace_id", "project_id", "meeting_title", "meeting_url",
            "meeting_type", "start_time", "end_time", "status",
            "ai_summary", "decisions", "action_items", "attendees",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "ai_summary", "decisions", "action_items", "created_at", "updated_at"]


class AIReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIReport
        fields = [
            "id", "workspace_id", "project_id", "trial_id",
            "report_type", "audience", "title", "content",
            "generated_by", "created_at",
        ]
        read_only_fields = fields


class AIReportListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer (no full content)."""
    class Meta:
        model = AIReport
        fields = [
            "id", "report_type", "audience", "title",
            "generated_by", "created_at",
        ]
