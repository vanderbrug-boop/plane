"""
API views for clinical trial management.

CRUD endpoints for submissions, CROs, trials, sites, and TMF documents.
All views are workspace-scoped and require authentication.
"""

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    CRO,
    CRODeliverable,
    CROKpi,
    ClinicalTrial,
    Submission,
    SubmissionSection,
    TMFDocument,
    TrialSite,
)
from .serializers import (
    CRODeliverableSerializer,
    CROKpiSerializer,
    CROSerializer,
    ClinicalTrialSerializer,
    SubmissionListSerializer,
    SubmissionSectionSerializer,
    SubmissionSerializer,
    TMFDocumentSerializer,
    TrialSiteSerializer,
)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

class SubmissionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return SubmissionListSerializer
        return SubmissionSerializer

    def get_queryset(self):
        qs = Submission.objects.filter(workspace_id=self.kwargs["workspace_id"])
        sub_type = self.request.query_params.get("type")
        if sub_type:
            qs = qs.filter(submission_type=sub_type)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.prefetch_related("sections")

    def perform_create(self, serializer):
        submission = serializer.save(workspace_id=self.kwargs["workspace_id"])
        # Auto-create standard sections based on submission type
        if submission.submission_type == "IND":
            sections = SubmissionSection.IND_SECTIONS
        elif submission.submission_type == "CTA":
            sections = SubmissionSection.CTA_SECTIONS
        else:
            sections = []

        for key, name in sections:
            SubmissionSection.objects.create(
                submission=submission,
                section_key=key,
                section_name=name,
            )


class SubmissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Submission.objects.filter(
            workspace_id=self.kwargs["workspace_id"]
        ).prefetch_related("sections")


class SubmissionSectionUpdateView(generics.UpdateAPIView):
    """Update a specific section of a submission."""
    serializer_class = SubmissionSectionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return SubmissionSection.objects.filter(
            submission__workspace_id=self.kwargs["workspace_id"]
        )


# ---------------------------------------------------------------------------
# CROs
# ---------------------------------------------------------------------------

class CROListCreateView(generics.ListCreateAPIView):
    serializer_class = CROSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CRO.objects.filter(workspace_id=self.kwargs["workspace_id"])
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(workspace_id=self.kwargs["workspace_id"])


class CRODetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CROSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return CRO.objects.filter(workspace_id=self.kwargs["workspace_id"])


class CRODeliverableListCreateView(generics.ListCreateAPIView):
    serializer_class = CRODeliverableSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CRODeliverable.objects.filter(
            cro__workspace_id=self.kwargs["workspace_id"]
        ).select_related("cro")

        cro_id = self.request.query_params.get("cro_id")
        if cro_id:
            qs = qs.filter(cro_id=cro_id)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        overdue = self.request.query_params.get("overdue")
        if overdue == "true":
            qs = qs.filter(
                due_date__lt=timezone.now().date(),
                status__in=["pending", "in_progress"],
            )

        return qs


class CROKpiListCreateView(generics.ListCreateAPIView):
    serializer_class = CROKpiSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CROKpi.objects.filter(
            cro__workspace_id=self.kwargs["workspace_id"]
        ).select_related("cro")

        cro_id = self.request.query_params.get("cro_id")
        if cro_id:
            qs = qs.filter(cro_id=cro_id)

        metric = self.request.query_params.get("metric")
        if metric:
            qs = qs.filter(metric_name=metric)

        return qs


class CRODashboardView(APIView):
    """
    Aggregate CRO performance dashboard.
    Returns summary stats for all CROs in a workspace.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        cros = CRO.objects.filter(workspace_id=workspace_id, status="active")
        today = timezone.now().date()

        dashboard = []
        for cro in cros:
            deliverables = cro.deliverables.all()
            total = deliverables.count()
            overdue = deliverables.filter(
                due_date__lt=today, status__in=["pending", "in_progress"]
            ).count()
            completed = deliverables.filter(status__in=["accepted", "delivered"]).count()

            recent_kpis = cro.kpis.order_by("-period_end")[:10]
            kpis_on_target = sum(1 for k in recent_kpis if k.on_target)
            kpis_total = recent_kpis.count()

            avg_quality = deliverables.filter(
                quality_score__isnull=False
            ).values_list("quality_score", flat=True)
            avg_quality = sum(avg_quality) / len(avg_quality) if avg_quality else None

            dashboard.append({
                "cro_id": str(cro.id),
                "cro_name": cro.name,
                "status": cro.status,
                "total_deliverables": total,
                "completed_deliverables": completed,
                "overdue_deliverables": overdue,
                "kpis_on_target": kpis_on_target,
                "kpis_total": kpis_total,
                "avg_quality_score": avg_quality,
                "contract_value": str(cro.contract_value) if cro.contract_value else None,
                "dpa_signed": cro.dpa_signed,
            })

        return Response(dashboard)


# ---------------------------------------------------------------------------
# Clinical Trials & Sites
# ---------------------------------------------------------------------------

class ClinicalTrialListCreateView(generics.ListCreateAPIView):
    serializer_class = ClinicalTrialSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ClinicalTrial.objects.filter(workspace_id=self.kwargs["workspace_id"])
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        phase = self.request.query_params.get("phase")
        if phase:
            qs = qs.filter(phase=phase)
        return qs.prefetch_related("sites")

    def perform_create(self, serializer):
        serializer.save(workspace_id=self.kwargs["workspace_id"])


class ClinicalTrialDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClinicalTrialSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return ClinicalTrial.objects.filter(
            workspace_id=self.kwargs["workspace_id"]
        ).prefetch_related("sites")


class TrialSiteListCreateView(generics.ListCreateAPIView):
    serializer_class = TrialSiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TrialSite.objects.filter(
            trial_id=self.kwargs["trial_id"]
        ).select_related("cro")

        country = self.request.query_params.get("country")
        if country:
            qs = qs.filter(country=country)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs


class TrialSiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TrialSiteSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return TrialSite.objects.filter(trial_id=self.kwargs["trial_id"]).select_related("cro")


class EnrollmentDashboardView(APIView):
    """
    Enrollment overview for a clinical trial.
    Returns per-country and per-site enrollment data.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, trial_id):
        trial = ClinicalTrial.objects.get(id=trial_id, workspace_id=workspace_id)
        sites = trial.sites.all().select_related("cro")

        by_country = {}
        for site in sites:
            c = site.country
            if c not in by_country:
                by_country[c] = {"target": 0, "actual": 0, "sites": 0, "active_sites": 0}
            by_country[c]["target"] += site.enrollment_target
            by_country[c]["actual"] += site.enrollment_actual
            by_country[c]["sites"] += 1
            if site.status in ("activated", "enrolling", "enrollment_complete"):
                by_country[c]["active_sites"] += 1

        return Response({
            "trial_id": str(trial.id),
            "protocol_number": trial.protocol_number,
            "phase": trial.phase,
            "target_enrollment": trial.target_enrollment,
            "current_enrollment": trial.current_enrollment,
            "enrollment_pct": trial.enrollment_pct,
            "screen_failure_rate": trial.screen_failure_rate,
            "by_country": by_country,
            "sites": TrialSiteSerializer(sites, many=True).data,
        })


# ---------------------------------------------------------------------------
# TMF Documents
# ---------------------------------------------------------------------------

class TMFDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = TMFDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TMFDocument.objects.filter(
            trial_id=self.kwargs["trial_id"]
        ).select_related("site")

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        required_only = self.request.query_params.get("required")
        if required_only == "true":
            qs = qs.filter(required=True)

        return qs


class TMFDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TMFDocumentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return TMFDocument.objects.filter(trial_id=self.kwargs["trial_id"])


class TMFReadinessView(APIView):
    """
    TMF readiness dashboard — shows completeness of essential documents.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, trial_id):
        docs = TMFDocument.objects.filter(trial_id=trial_id)
        required_docs = docs.filter(required=True)

        total_required = required_docs.count()
        approved = required_docs.filter(status="approved").count()
        missing = required_docs.filter(status="missing").count()
        in_progress = required_docs.filter(status__in=["draft", "review"]).count()

        by_category = {}
        for cat_value, cat_label in TMFDocument.Category.choices:
            cat_docs = required_docs.filter(category=cat_value)
            cat_total = cat_docs.count()
            if cat_total == 0:
                continue
            by_category[cat_value] = {
                "label": cat_label,
                "total": cat_total,
                "approved": cat_docs.filter(status="approved").count(),
                "missing": cat_docs.filter(status="missing").count(),
                "in_progress": cat_docs.filter(status__in=["draft", "review"]).count(),
            }

        return Response({
            "trial_id": str(trial_id),
            "total_required": total_required,
            "approved": approved,
            "missing": missing,
            "in_progress": in_progress,
            "readiness_pct": round(100 * approved / total_required, 1) if total_required > 0 else 0,
            "by_category": by_category,
        })
