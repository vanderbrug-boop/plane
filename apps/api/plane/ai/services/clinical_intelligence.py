"""
AI-powered clinical trial intelligence services.

Provides:
- Natural language querying of clinical trial data
- Enrollment forecasting
- CRO performance monitoring & scorecards
- Regulatory submission gap analysis
- Meeting summarization (CRO calls, investigator, regulatory, internal)
- Automated status report generation
"""

import json
import logging
from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from ...clinical.models import (
    CRO,
    CRODeliverable,
    CROKpi,
    ClinicalTrial,
    Submission,
    SubmissionSection,
    TMFDocument,
    TrialSite,
)
from ..models import AIReport, ScheduledMeeting
from . import prompt_manager
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ClinicalIntelligenceService:
    """Orchestrates all AI-powered clinical trial features."""

    def __init__(self, workspace_id: str, user_id: str = None):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.client = ClaudeClient(workspace_id=workspace_id, user_id=user_id)

    # ------------------------------------------------------------------
    # Natural Language Query
    # ------------------------------------------------------------------

    def natural_language_query(self, question: str) -> dict[str, Any]:
        """
        Answer a natural language question about clinical trial data.
        Uses Claude tool-use to query the database and synthesize an answer.
        """
        tool_handlers = {
            "query_submissions": self._tool_query_submissions,
            "query_cro_performance": self._tool_query_cro_performance,
            "query_enrollment": self._tool_query_enrollment,
            "query_sites": self._tool_query_sites,
            "query_tmf_status": self._tool_query_tmf_status,
            "query_deliverables": self._tool_query_deliverables,
            "query_trial_overview": self._tool_query_trial_overview,
        }

        result = self.client.complete_with_tools(
            feature="nl_query",
            system=prompt_manager.NATURAL_LANGUAGE_QUERY,
            messages=[{"role": "user", "content": question}],
            tools=prompt_manager.NL_QUERY_TOOLS,
            tool_handlers=tool_handlers,
            max_turns=5,
            request_summary=f"NL query: {question[:100]}",
        )

        return {
            "answer": result["content"],
            "tool_calls": result.get("all_tool_calls", []),
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # Enrollment Forecasting
    # ------------------------------------------------------------------

    def forecast_enrollment(self, trial_id: str) -> dict[str, Any]:
        """
        Analyze enrollment data and forecast trial completion.
        """
        trial = ClinicalTrial.objects.get(id=trial_id, workspace_id=self.workspace_id)
        sites = trial.sites.all().select_related("cro")

        # Build enrollment data snapshot
        enrollment_data = {
            "trial": {
                "protocol_number": trial.protocol_number,
                "phase": trial.phase,
                "target_enrollment": trial.target_enrollment,
                "current_enrollment": trial.current_enrollment,
                "screen_failure_count": trial.screen_failure_count,
                "status": trial.status,
                "first_patient_in": str(trial.first_patient_in) if trial.first_patient_in else None,
                "first_site_activated": str(trial.first_site_activated) if trial.first_site_activated else None,
            },
            "sites": [],
            "today": str(date.today()),
        }

        for site in sites:
            enrollment_data["sites"].append({
                "site_name": site.site_name,
                "country": site.country,
                "cro": site.cro.name if site.cro else "Direct",
                "status": site.status,
                "activation_date": str(site.activation_date) if site.activation_date else None,
                "enrollment_target": site.enrollment_target,
                "enrollment_actual": site.enrollment_actual,
                "screen_failure_count": site.screen_failure_count,
                "screen_failure_rate": site.screen_failure_rate,
            })

        result = self.client.complete(
            feature="enrollment_forecast",
            system=prompt_manager.ENROLLMENT_FORECAST,
            messages=[{
                "role": "user",
                "content": f"Analyze this enrollment data and provide a forecast:\n\n{json.dumps(enrollment_data, indent=2)}",
            }],
            max_tokens=4096,
            request_summary=f"Enrollment forecast for trial {trial.protocol_number}",
        )

        return {
            "forecast": result["content"],
            "data_snapshot": enrollment_data,
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # CRO Performance Monitoring
    # ------------------------------------------------------------------

    def generate_cro_scorecard(self, cro_id: str = None) -> dict[str, Any]:
        """
        Generate AI-powered CRO performance scorecards.
        If cro_id is None, generates scorecards for all active CROs.
        """
        if cro_id:
            cros = CRO.objects.filter(id=cro_id, workspace_id=self.workspace_id)
        else:
            cros = CRO.objects.filter(workspace_id=self.workspace_id, status="active")

        cro_data = []
        for cro in cros:
            deliverables = cro.deliverables.all()
            kpis = cro.kpis.order_by("-period_end")[:20]
            today = date.today()

            cro_entry = {
                "name": cro.name,
                "services": cro.services,
                "regions": cro.regions,
                "contract_value": str(cro.contract_value) if cro.contract_value else None,
                "deliverables": {
                    "total": deliverables.count(),
                    "completed": deliverables.filter(status__in=["accepted", "delivered"]).count(),
                    "overdue": deliverables.filter(due_date__lt=today, status__in=["pending", "in_progress"]).count(),
                    "upcoming_7_days": deliverables.filter(
                        due_date__range=[today, today + timedelta(days=7)],
                        status__in=["pending", "in_progress"],
                    ).count(),
                    "avg_quality_score": deliverables.filter(
                        quality_score__isnull=False
                    ).aggregate(avg=Avg("quality_score"))["avg"],
                },
                "kpis": [
                    {
                        "metric": k.metric_name,
                        "period": f"{k.period_start} to {k.period_end}",
                        "target": float(k.target_value),
                        "actual": float(k.actual_value),
                        "on_target": k.on_target,
                    }
                    for k in kpis
                ],
            }
            cro_data.append(cro_entry)

        result = self.client.complete(
            feature="cro_scorecard",
            system=prompt_manager.CRO_PERFORMANCE,
            messages=[{
                "role": "user",
                "content": f"Generate performance scorecards for these CROs:\n\n{json.dumps(cro_data, indent=2)}",
            }],
            max_tokens=4096,
            request_summary=f"CRO scorecard for {len(cro_data)} CRO(s)",
        )

        return {
            "scorecard": result["content"],
            "data_snapshot": cro_data,
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # Regulatory Intelligence
    # ------------------------------------------------------------------

    def regulatory_gap_analysis(self) -> dict[str, Any]:
        """
        Analyze all regulatory submissions for gaps, risks, and upcoming deadlines.
        """
        submissions = Submission.objects.filter(
            workspace_id=self.workspace_id
        ).exclude(status__in=["approved", "withdrawn"]).prefetch_related("sections")

        sub_data = []
        for sub in submissions:
            sections = sub.sections.all()
            sub_entry = {
                "type": sub.submission_type,
                "authority": sub.authority,
                "country": sub.country,
                "status": sub.status,
                "submitted_at": str(sub.submitted_at) if sub.submitted_at else None,
                "review_deadline": str(sub.review_deadline) if sub.review_deadline else None,
                "review_days_remaining": sub.review_days_remaining,
                "is_overdue": sub.is_overdue,
                "sections": [
                    {
                        "name": s.section_name,
                        "status": s.status,
                        "completion_pct": s.completion_pct,
                        "due_date": str(s.due_date) if s.due_date else None,
                        "assigned_to": str(s.assigned_to) if s.assigned_to else "Unassigned",
                    }
                    for s in sections
                ],
            }
            sub_data.append(sub_entry)

        result = self.client.complete(
            feature="regulatory_intel",
            system=prompt_manager.REGULATORY_INTELLIGENCE,
            messages=[{
                "role": "user",
                "content": (
                    f"Analyze these regulatory submissions and identify gaps, risks, and priorities.\n"
                    f"Today's date: {date.today()}\n\n{json.dumps(sub_data, indent=2)}"
                ),
            }],
            max_tokens=4096,
            request_summary=f"Regulatory gap analysis for {len(sub_data)} submission(s)",
        )

        return {
            "analysis": result["content"],
            "data_snapshot": sub_data,
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # Meeting Summarization
    # ------------------------------------------------------------------

    def summarize_meeting(self, meeting_id: str) -> dict[str, Any]:
        """
        Summarize a meeting transcript using meeting-type-specific prompts.
        """
        meeting = ScheduledMeeting.objects.get(id=meeting_id, workspace_id=self.workspace_id)

        system_prompt = prompt_manager.MEETING_SUMMARIZATION.get(
            meeting.meeting_type,
            prompt_manager.MEETING_SUMMARIZATION["default"],
        )

        result = self.client.complete(
            feature="meeting_summary",
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"Meeting: {meeting.meeting_title}\n"
                    f"Type: {meeting.get_meeting_type_display()}\n"
                    f"Date: {meeting.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Attendees: {', '.join(meeting.attendees)}\n\n"
                    f"Transcript:\n{meeting.raw_transcript}"
                ),
            }],
            max_tokens=4096,
            request_summary=f"Meeting summary: {meeting.meeting_title[:50]}",
        )

        # Parse action items from structured response
        meeting.ai_summary = result["content"]
        meeting.status = ScheduledMeeting.Status.COMPLETED
        meeting.save(update_fields=["ai_summary", "status", "updated_at"])

        return {
            "summary": result["content"],
            "meeting_id": str(meeting.id),
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # Status Report Generation
    # ------------------------------------------------------------------

    def generate_status_report(
        self,
        report_type: str,
        trial_id: str = None,
        audience: str = "team",
    ) -> dict[str, Any]:
        """
        Generate an AI-powered status report.
        """
        data_snapshot = self._gather_report_data(report_type, trial_id)
        system_prompt = prompt_manager.STATUS_REPORT.get(
            report_type,
            prompt_manager.STATUS_REPORT["trial_status"],
        )

        result = self.client.complete(
            feature="status_report",
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate a {report_type} report for audience: {audience}.\n"
                    f"Today's date: {date.today()}\n\n"
                    f"Data:\n{json.dumps(data_snapshot, indent=2)}"
                ),
            }],
            max_tokens=8192,
            request_summary=f"Status report: {report_type} for {audience}",
        )

        # Save the report
        report = AIReport.objects.create(
            workspace_id=self.workspace_id,
            trial_id=trial_id,
            report_type=report_type,
            audience=audience,
            title=f"{report_type.replace('_', ' ').title()} - {date.today()}",
            content=result["content"],
            data_snapshot=data_snapshot,
            generated_by=self.user_id,
        )

        return {
            "report_id": str(report.id),
            "content": result["content"],
            "data_snapshot": data_snapshot,
            "usage": result["usage"],
        }

    # ------------------------------------------------------------------
    # Tool Handlers for Natural Language Query
    # ------------------------------------------------------------------

    def _tool_query_submissions(self, params: dict) -> dict:
        qs = Submission.objects.filter(workspace_id=self.workspace_id)
        if params.get("submission_type"):
            qs = qs.filter(submission_type=params["submission_type"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("country"):
            qs = qs.filter(country=params["country"])

        results = []
        for sub in qs.prefetch_related("sections")[:20]:
            results.append({
                "id": str(sub.id),
                "type": sub.submission_type,
                "authority": sub.authority,
                "country": sub.country,
                "status": sub.status,
                "review_days_remaining": sub.review_days_remaining,
                "is_overdue": sub.is_overdue,
                "sections": [
                    {"name": s.section_name, "status": s.status, "completion_pct": s.completion_pct}
                    for s in sub.sections.all()
                ],
            })
        return {"submissions": results, "count": len(results)}

    def _tool_query_cro_performance(self, params: dict) -> dict:
        qs = CRO.objects.filter(workspace_id=self.workspace_id)
        if params.get("cro_name"):
            qs = qs.filter(name__icontains=params["cro_name"])

        results = []
        for cro in qs[:10]:
            entry = {"id": str(cro.id), "name": cro.name, "status": cro.status, "services": cro.services}
            if params.get("include_deliverables", True):
                deliverables = cro.deliverables.all()
                today = date.today()
                entry["deliverables"] = {
                    "total": deliverables.count(),
                    "completed": deliverables.filter(status__in=["accepted", "delivered"]).count(),
                    "overdue": deliverables.filter(due_date__lt=today, status__in=["pending", "in_progress"]).count(),
                }
            if params.get("include_kpis", True):
                kpis = cro.kpis.order_by("-period_end")[:10]
                entry["recent_kpis"] = [
                    {"metric": k.metric_name, "target": float(k.target_value), "actual": float(k.actual_value), "on_target": k.on_target}
                    for k in kpis
                ]
            results.append(entry)
        return {"cros": results, "count": len(results)}

    def _tool_query_enrollment(self, params: dict) -> dict:
        qs = TrialSite.objects.filter(trial__workspace_id=self.workspace_id)
        if params.get("trial_id"):
            qs = qs.filter(trial_id=params["trial_id"])
        if params.get("country"):
            qs = qs.filter(country=params["country"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])

        sites = qs.select_related("trial", "cro")[:50]
        results = []
        for site in sites:
            results.append({
                "site_name": site.site_name,
                "country": site.country,
                "cro": site.cro.name if site.cro else "Direct",
                "status": site.status,
                "enrollment_target": site.enrollment_target,
                "enrollment_actual": site.enrollment_actual,
                "enrollment_pct": site.enrollment_pct,
                "screen_failure_rate": site.screen_failure_rate,
                "activation_date": str(site.activation_date) if site.activation_date else None,
            })

        total_target = sum(s["enrollment_target"] for s in results)
        total_actual = sum(s["enrollment_actual"] for s in results)

        return {
            "sites": results,
            "summary": {
                "total_target": total_target,
                "total_actual": total_actual,
                "overall_pct": round(100 * total_actual / total_target, 1) if total_target > 0 else 0,
                "site_count": len(results),
            },
        }

    def _tool_query_sites(self, params: dict) -> dict:
        qs = TrialSite.objects.filter(trial__workspace_id=self.workspace_id)
        if params.get("trial_id"):
            qs = qs.filter(trial_id=params["trial_id"])
        if params.get("country"):
            qs = qs.filter(country=params["country"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("cro_id"):
            qs = qs.filter(cro_id=params["cro_id"])

        sites = qs.select_related("cro")[:50]
        return {
            "sites": [
                {
                    "id": str(s.id),
                    "site_name": s.site_name,
                    "country": s.country,
                    "city": s.city,
                    "pi": s.principal_investigator,
                    "cro": s.cro.name if s.cro else "Direct",
                    "irb_ec_status": s.irb_ec_status,
                    "status": s.status,
                    "activation_date": str(s.activation_date) if s.activation_date else None,
                    "enrollment": f"{s.enrollment_actual}/{s.enrollment_target}",
                }
                for s in sites
            ],
            "count": len(sites),
        }

    def _tool_query_tmf_status(self, params: dict) -> dict:
        qs = TMFDocument.objects.filter(trial__workspace_id=self.workspace_id)
        if params.get("trial_id"):
            qs = qs.filter(trial_id=params["trial_id"])
        if params.get("category"):
            qs = qs.filter(category=params["category"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("required_only", True):
            qs = qs.filter(required=True)

        total = qs.count()
        by_status = {}
        for status_val, status_label in TMFDocument.Status.choices:
            count = qs.filter(status=status_val).count()
            if count > 0:
                by_status[status_val] = count

        missing_docs = list(
            qs.filter(status="missing").values_list("document_name", "category")[:20]
        )

        return {
            "total_documents": total,
            "by_status": by_status,
            "readiness_pct": round(100 * by_status.get("approved", 0) / total, 1) if total > 0 else 0,
            "missing_documents": [{"name": name, "category": cat} for name, cat in missing_docs],
        }

    def _tool_query_deliverables(self, params: dict) -> dict:
        qs = CRODeliverable.objects.filter(cro__workspace_id=self.workspace_id)
        if params.get("cro_id"):
            qs = qs.filter(cro_id=params["cro_id"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("overdue_only"):
            qs = qs.filter(due_date__lt=date.today(), status__in=["pending", "in_progress"])

        deliverables = qs.select_related("cro")[:30]
        return {
            "deliverables": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "cro": d.cro.name,
                    "status": d.status,
                    "due_date": str(d.due_date),
                    "is_overdue": d.is_overdue,
                    "days_until_due": d.days_until_due,
                    "quality_score": d.quality_score,
                }
                for d in deliverables
            ],
            "count": len(deliverables),
        }

    def _tool_query_trial_overview(self, params: dict) -> dict:
        qs = ClinicalTrial.objects.filter(workspace_id=self.workspace_id)
        if params.get("trial_id"):
            qs = qs.filter(id=params["trial_id"])

        trials = qs.prefetch_related("sites")[:10]
        return {
            "trials": [
                {
                    "id": str(t.id),
                    "protocol_number": t.protocol_number,
                    "phase": t.phase,
                    "indication": t.indication,
                    "status": t.status,
                    "target_enrollment": t.target_enrollment,
                    "current_enrollment": t.current_enrollment,
                    "enrollment_pct": t.enrollment_pct,
                    "site_count": t.sites.count(),
                    "first_patient_in": str(t.first_patient_in) if t.first_patient_in else None,
                    "last_patient_in": str(t.last_patient_in) if t.last_patient_in else None,
                }
                for t in trials
            ],
        }

    # ------------------------------------------------------------------
    # Helper: Gather report data
    # ------------------------------------------------------------------

    def _gather_report_data(self, report_type: str, trial_id: str = None) -> dict:
        data = {"generated_at": str(date.today())}

        if trial_id:
            trial = ClinicalTrial.objects.get(id=trial_id, workspace_id=self.workspace_id)
            sites = trial.sites.all().select_related("cro")
            data["trial"] = {
                "protocol_number": trial.protocol_number,
                "phase": trial.phase,
                "indication": trial.indication,
                "status": trial.status,
                "target_enrollment": trial.target_enrollment,
                "current_enrollment": trial.current_enrollment,
                "enrollment_pct": trial.enrollment_pct,
                "screen_failure_rate": trial.screen_failure_rate,
                "first_patient_in": str(trial.first_patient_in) if trial.first_patient_in else None,
            }
            data["sites_by_country"] = {}
            for site in sites:
                c = site.country
                if c not in data["sites_by_country"]:
                    data["sites_by_country"][c] = {"target": 0, "actual": 0, "sites": 0}
                data["sites_by_country"][c]["target"] += site.enrollment_target
                data["sites_by_country"][c]["actual"] += site.enrollment_actual
                data["sites_by_country"][c]["sites"] += 1

        # Submissions
        subs = Submission.objects.filter(workspace_id=self.workspace_id).exclude(status="withdrawn")
        data["submissions"] = [
            {
                "type": s.submission_type, "authority": s.authority, "country": s.country,
                "status": s.status, "review_days_remaining": s.review_days_remaining,
            }
            for s in subs[:20]
        ]

        # CROs
        if report_type in ("cro_oversight", "executive_summary", "board_update"):
            cros = CRO.objects.filter(workspace_id=self.workspace_id, status="active")
            data["cros"] = []
            for cro in cros:
                today = date.today()
                deliverables = cro.deliverables.all()
                data["cros"].append({
                    "name": cro.name,
                    "total_deliverables": deliverables.count(),
                    "overdue": deliverables.filter(due_date__lt=today, status__in=["pending", "in_progress"]).count(),
                    "completed": deliverables.filter(status__in=["accepted", "delivered"]).count(),
                })

        return data
