"""
Celery tasks for scheduled AI operations.

- Calendar polling for upcoming meetings
- Automated meeting bot deployment
- Scheduled status report generation
- Monthly token budget reset
"""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


# In a Plane fork, these would use: from celery import shared_task
# For now, we define the task functions that Celery would call.


def poll_calendars():
    """
    Celery beat task: Poll connected calendars for upcoming meetings.
    Runs every 15 minutes. Detects meetings with video call links
    and schedules Recall.ai bot deployment.
    """
    from .models import CalendarConnection, ScheduledMeeting

    connections = CalendarConnection.objects.filter(auto_join_enabled=True)

    for conn in connections:
        try:
            # In production: use Google Calendar API / Microsoft Graph API
            # to fetch events in the next 30 minutes
            logger.info(
                f"Polling {conn.provider} calendar for user {conn.user_id}"
            )
            # events = fetch_calendar_events(conn, minutes_ahead=30)
            # for event in events:
            #     if has_video_link(event):
            #         ScheduledMeeting.objects.get_or_create(
            #             calendar_connection=conn,
            #             meeting_url=event.video_link,
            #             start_time=event.start_time,
            #             defaults={...}
            #         )
        except Exception as e:
            logger.error(f"Calendar poll failed for {conn.id}: {e}")


def deploy_meeting_bots():
    """
    Celery beat task: Deploy Recall.ai bots for upcoming meetings.
    Runs every 5 minutes. Joins meetings that start within 2 minutes.
    """
    from .models import ScheduledMeeting

    now = timezone.now()
    upcoming = ScheduledMeeting.objects.filter(
        status="scheduled",
        start_time__lte=now + timedelta(minutes=2),
        start_time__gte=now - timedelta(minutes=5),
    )

    for meeting in upcoming:
        try:
            logger.info(f"Deploying bot for meeting: {meeting.meeting_title}")
            # In production:
            # bot = recall_client.create_bot(meeting.meeting_url)
            # meeting.recall_bot_id = bot.id
            # meeting.status = "bot_joining"
            # meeting.save()
        except Exception as e:
            logger.error(f"Bot deployment failed for meeting {meeting.id}: {e}")
            meeting.status = "failed"
            meeting.save(update_fields=["status"])


def generate_scheduled_reports():
    """
    Celery beat task: Generate scheduled status reports.
    Runs daily at configured time.
    """
    from .models import AIWorkspaceConfig
    from .services.clinical_intelligence import ClinicalIntelligenceService

    configs = AIWorkspaceConfig.objects.filter(
        features_enabled__has_key="scheduled_reports"
    )

    for config in configs:
        try:
            if not config.features_enabled.get("scheduled_reports"):
                continue

            service = ClinicalIntelligenceService(
                workspace_id=str(config.workspace_id)
            )

            # Generate daily trial status for team
            service.generate_status_report(
                report_type="trial_status",
                audience="team",
            )

            logger.info(f"Generated scheduled report for workspace {config.workspace_id}")
        except Exception as e:
            logger.error(f"Scheduled report failed for workspace {config.workspace_id}: {e}")


def reset_monthly_token_budgets():
    """
    Celery beat task: Reset monthly token usage counters.
    Runs on the 1st of each month.
    """
    from .models import AIWorkspaceConfig

    today = timezone.now().date()
    configs = AIWorkspaceConfig.objects.all()

    for config in configs:
        if config.budget_reset_date is None or config.budget_reset_date <= today:
            config.tokens_used_this_month = 0
            config.budget_reset_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            config.save(update_fields=["tokens_used_this_month", "budget_reset_date"])
            logger.info(f"Reset token budget for workspace {config.workspace_id}")


# Celery beat schedule (would go in celeryconfig.py in a Plane fork):
#
# CELERY_BEAT_SCHEDULE = {
#     'poll-calendars': {
#         'task': 'plane.ai.tasks.poll_calendars',
#         'schedule': crontab(minute='*/15'),
#     },
#     'deploy-meeting-bots': {
#         'task': 'plane.ai.tasks.deploy_meeting_bots',
#         'schedule': crontab(minute='*/5'),
#     },
#     'generate-scheduled-reports': {
#         'task': 'plane.ai.tasks.generate_scheduled_reports',
#         'schedule': crontab(hour=8, minute=0),  # 8am daily
#     },
#     'reset-token-budgets': {
#         'task': 'plane.ai.tasks.reset_monthly_token_budgets',
#         'schedule': crontab(day_of_month=1, hour=0, minute=0),
#     },
# }
