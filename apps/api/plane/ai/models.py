"""
AI service models — configuration, usage tracking, meeting management.
"""

import uuid

from django.db import models
from django.utils import timezone


class AIWorkspaceConfig(models.Model):
    """Per-workspace AI configuration. Stores API keys, model preferences, budgets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(unique=True)

    # LLM provider config
    provider = models.CharField(max_length=20, default="anthropic")
    api_key_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="Encrypted API key (use Fernet or similar)",
    )
    model = models.CharField(max_length=100, default="claude-sonnet-4-6")

    # Token budget
    monthly_token_budget = models.BigIntegerField(default=1_000_000)
    tokens_used_this_month = models.BigIntegerField(default=0)
    budget_reset_date = models.DateField(null=True, blank=True)

    # Feature toggles
    features_enabled = models.JSONField(
        default=dict,
        help_text="Feature flags: task_intelligence, communication_ai, enrollment_forecast, etc.",
    )

    # Meeting bot config
    recall_api_key_encrypted = models.TextField(blank=True, default="")
    auto_join_meetings = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_workspace_config"

    def __str__(self):
        return f"AI Config for workspace {self.workspace_id}"

    def has_budget(self, estimated_tokens=1000):
        return (self.tokens_used_this_month + estimated_tokens) <= self.monthly_token_budget

    def record_usage(self, input_tokens, output_tokens):
        self.tokens_used_this_month += input_tokens + output_tokens
        self.save(update_fields=["tokens_used_this_month"])


class AIUsageLog(models.Model):
    """
    Tracks every AI API call for cost management and audit compliance.
    Per 21 CFR Part 11: AI-generated content that informs decisions must be traceable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True, null=True, blank=True)

    feature = models.CharField(
        max_length=50,
        db_index=True,
        help_text="e.g., 'nl_query', 'status_report', 'enrollment_forecast', 'cro_scorecard'",
    )
    model = models.CharField(max_length=100)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)

    # Minimal logging for GDPR compliance (don't store full prompts with PII)
    request_summary = models.TextField(
        blank=True,
        default="",
        help_text="Brief description of what was asked (no PII)",
    )
    response_summary = models.TextField(
        blank=True,
        default="",
        help_text="Brief summary of what was returned",
    )
    duration_ms = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "ai_usage_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.feature} ({self.input_tokens}+{self.output_tokens} tokens)"


class CalendarConnection(models.Model):
    """OAuth connection to Google Calendar or Microsoft Outlook."""

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google Calendar"
        MICROSOFT = "microsoft", "Microsoft Outlook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)

    provider = models.CharField(max_length=20, choices=Provider.choices)
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField(blank=True, default="")
    token_expiry = models.DateTimeField(null=True, blank=True)
    calendar_id = models.CharField(max_length=255, blank=True, default="primary")
    auto_join_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_calendar_connections"
        unique_together = ["user_id", "provider"]

    def __str__(self):
        return f"{self.provider} calendar for user {self.user_id}"


class ScheduledMeeting(models.Model):
    """Meetings detected from calendar that the bot will join."""

    class MeetingType(models.TextChoices):
        CRO_OVERSIGHT = "cro_oversight", "CRO Oversight Call"
        INVESTIGATOR = "investigator", "Investigator Meeting"
        REGULATORY = "regulatory", "Regulatory Strategy"
        INTERNAL = "internal", "Internal Team Meeting"
        BOARD = "board", "Board/Investor Meeting"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        BOT_JOINING = "bot_joining", "Bot Joining"
        IN_PROGRESS = "in_progress", "In Progress"
        TRANSCRIBING = "transcribing", "Transcribing"
        SUMMARIZING = "summarizing", "Summarizing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar_connection = models.ForeignKey(
        CalendarConnection,
        on_delete=models.CASCADE,
        related_name="meetings",
    )
    workspace_id = models.UUIDField(db_index=True)
    project_id = models.UUIDField(null=True, blank=True)

    meeting_title = models.CharField(max_length=255)
    meeting_url = models.URLField(max_length=512)
    meeting_type = models.CharField(
        max_length=20,
        choices=MeetingType.choices,
        default=MeetingType.OTHER,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    recall_bot_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Recall.ai bot instance ID",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    # Results
    raw_transcript = models.TextField(blank=True, default="")
    ai_summary = models.TextField(blank=True, default="")
    decisions = models.JSONField(default=list)
    action_items = models.JSONField(
        default=list,
        help_text="[{task, owner, deadline, created_issue_id}]",
    )
    attendees = models.JSONField(default=list)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_scheduled_meetings"
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.meeting_title} ({self.meeting_type}) - {self.status}"


class AIReport(models.Model):
    """AI-generated reports (status reports, CRO scorecards, regulatory updates)."""

    class ReportType(models.TextChoices):
        TRIAL_STATUS = "trial_status", "Trial Status Report"
        CRO_OVERSIGHT = "cro_oversight", "CRO Oversight Report"
        REGULATORY_UPDATE = "regulatory_update", "Regulatory Update"
        EXECUTIVE_SUMMARY = "executive_summary", "Executive Summary"
        BOARD_UPDATE = "board_update", "Board/Investor Update"
        ENROLLMENT_FORECAST = "enrollment_forecast", "Enrollment Forecast"

    class Audience(models.TextChoices):
        TEAM = "team", "Internal Team"
        EXECUTIVE = "executive", "Executive Leadership"
        BOARD = "board", "Board of Directors"
        INVESTOR = "investor", "Investors"
        REGULATORY = "regulatory", "Regulatory Authority"
        CRO = "cro", "CRO Partner"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    project_id = models.UUIDField(null=True, blank=True)
    trial_id = models.UUIDField(null=True, blank=True)

    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.TEAM)
    title = models.CharField(max_length=255)
    content = models.TextField()
    data_snapshot = models.JSONField(
        default=dict,
        help_text="Structured data used to generate this report (for verification)",
    )

    generated_by = models.UUIDField(null=True, blank=True, help_text="User who triggered generation")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "ai_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.report_type}) - {self.created_at.date()}"
