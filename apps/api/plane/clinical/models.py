"""
Clinical trial domain models.

Covers the full lifecycle of clinical trial management:
- IND (FDA) and CTA (EMA) regulatory submissions
- CRO (Contract Research Organization) management
- Clinical trial milestones and site tracking
- TMF (Trial Master File) document management
"""

import uuid

from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# IND / CTA Submission Tracking
# ---------------------------------------------------------------------------

class Submission(models.Model):
    """
    Tracks IND (FDA) and CTA (EMA/national authority) regulatory submissions.
    Includes review clock tracking (30 days for IND, 60 days for CTA).
    """

    class SubmissionType(models.TextChoices):
        IND = "IND", "Investigational New Drug (FDA)"
        CTA = "CTA", "Clinical Trial Application (EMA)"
        AMENDMENT = "AMENDMENT", "Protocol Amendment"
        ANNUAL_REPORT = "ANNUAL_REPORT", "Annual Report"

    class Status(models.TextChoices):
        DRAFTING = "drafting", "Drafting"
        INTERNAL_REVIEW = "internal_review", "Internal Review"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        QUESTIONS_RECEIVED = "questions_received", "Questions Received"
        APPROVED = "approved", "Approved"
        CLINICAL_HOLD = "clinical_hold", "Clinical Hold"
        PARTIAL_HOLD = "partial_hold", "Partial Clinical Hold"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    AUTHORITY_CHOICES = [
        ("FDA", "U.S. Food and Drug Administration"),
        ("EMA", "European Medicines Agency"),
        ("MHRA", "Medicines and Healthcare products Regulatory Agency (UK)"),
        ("BfArM", "Federal Institute for Drugs and Medical Devices (Germany)"),
        ("ANSM", "National Agency for Medicines Safety (France)"),
        ("AIFA", "Italian Medicines Agency"),
        ("AEMPS", "Spanish Agency of Medicines"),
        ("Swissmedic", "Swiss Agency for Therapeutic Products"),
        ("PMDA", "Pharmaceuticals and Medical Devices Agency (Japan)"),
        ("Health_Canada", "Health Canada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    project_id = models.UUIDField(db_index=True)

    submission_type = models.CharField(max_length=20, choices=SubmissionType.choices)
    authority = models.CharField(max_length=50, choices=AUTHORITY_CHOICES)
    country = models.CharField(max_length=5, help_text="ISO 3166-1 alpha-2 country code")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFTING)

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="IND number or CTA reference number",
    )
    protocol_number = models.CharField(max_length=100, blank=True, default="")

    submitted_at = models.DateTimeField(null=True, blank=True)
    review_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="30 days post-submission (IND) or 60 days (CTA)",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_submissions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace_id", "submission_type"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.submission_type} - {self.authority} ({self.country}) [{self.status}]"

    @property
    def review_days_remaining(self):
        if not self.review_deadline:
            return None
        delta = self.review_deadline - timezone.now()
        return max(0, delta.days)

    @property
    def is_overdue(self):
        if not self.review_deadline:
            return False
        return timezone.now() > self.review_deadline and self.status == self.Status.UNDER_REVIEW


class SubmissionSection(models.Model):
    """
    Tracks each section/module of a regulatory submission.
    For IND: CMC, Nonclinical, Clinical, etc.
    For CTA: Product info, Protocol, IB, GMP, etc.
    """

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        DRAFT_COMPLETE = "draft_complete", "Draft Complete"
        REVIEW = "review", "Under Review"
        FINALIZED = "finalized", "Finalized"

    IND_SECTIONS = [
        ("cover_letter", "Cover Letter"),
        ("form_1571", "Form FDA 1571"),
        ("toc", "Table of Contents"),
        ("introductory_statement", "Introductory Statement"),
        ("general_investigational_plan", "General Investigational Plan"),
        ("investigators_brochure", "Investigator's Brochure"),
        ("clinical_protocol", "Clinical Protocol"),
        ("cmc", "Chemistry, Manufacturing, and Controls"),
        ("pharmacology_toxicology", "Pharmacology and Toxicology"),
        ("previous_human_experience", "Previous Human Experience"),
        ("additional_information", "Additional Information"),
    ]

    CTA_SECTIONS = [
        ("cover_letter", "Cover Letter"),
        ("application_form", "Application Form"),
        ("protocol", "Clinical Trial Protocol"),
        ("investigators_brochure", "Investigator's Brochure"),
        ("imp_dossier", "IMP Dossier (Quality Data)"),
        ("gmp_compliance", "GMP Compliance"),
        ("labelling", "Labelling of IMP"),
        ("subject_info", "Subject Information Sheet & ICF"),
        ("insurance", "Insurance/Indemnity"),
        ("financial_arrangements", "Financial Arrangements"),
        ("investigator_cv", "Investigator CV & Suitability"),
        ("ethics_approval", "Ethics Committee Opinion"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_key = models.CharField(max_length=50)
    section_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    assigned_to = models.UUIDField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completion_pct = models.IntegerField(default=0)
    document_url = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_submission_sections"
        ordering = ["submission", "section_key"]
        unique_together = ["submission", "section_key"]

    def __str__(self):
        return f"{self.section_name} [{self.status}] ({self.completion_pct}%)"


# ---------------------------------------------------------------------------
# CRO Management
# ---------------------------------------------------------------------------

class CRO(models.Model):
    """
    Contract Research Organization tracking.
    Manages CRO contracts, contacts, services, and GDPR DPA status.
    """

    class Status(models.TextChoices):
        PROSPECTIVE = "prospective", "Prospective"
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On Hold"
        TERMINATED = "terminated", "Terminated"

    SERVICE_TYPES = [
        "site_management",
        "data_management",
        "biostatistics",
        "medical_monitoring",
        "pharmacovigilance",
        "regulatory_affairs",
        "central_lab",
        "imaging",
        "supply_management",
        "monitoring",
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=50, blank=True, default="")

    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    contract_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    contract_currency = models.CharField(max_length=3, default="USD")

    services = models.JSONField(
        default=list,
        help_text="List of service types provided by this CRO",
    )
    regions = models.JSONField(
        default=list,
        help_text="Regions/countries where CRO operates for this engagement",
    )

    dpa_signed = models.BooleanField(default=False, help_text="GDPR Data Processing Agreement")
    dpa_signed_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROSPECTIVE)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_cros"
        ordering = ["name"]
        verbose_name = "CRO"
        verbose_name_plural = "CROs"

    def __str__(self):
        return f"{self.name} ({self.status})"


class CRODeliverable(models.Model):
    """
    Tracks specific deliverables owed by a CRO, with due dates,
    status, milestone payments, and quality scoring.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        DELIVERED = "delivered", "Delivered"
        UNDER_REVIEW = "under_review", "Under Review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        OVERDUE = "overdue", "Overdue"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cro = models.ForeignKey(CRO, on_delete=models.CASCADE, related_name="deliverables")
    project_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    category = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="e.g., 'site_activation', 'database', 'monitoring_report'",
    )

    due_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    milestone_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    quality_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="1-5 rating after acceptance",
    )
    review_notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_cro_deliverables"
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.title} - {self.cro.name} [{self.status}]"

    @property
    def is_overdue(self):
        if self.status in (self.Status.ACCEPTED, self.Status.DELIVERED):
            return False
        return self.due_date < timezone.now().date()

    @property
    def days_until_due(self):
        delta = self.due_date - timezone.now().date()
        return delta.days


class CROKpi(models.Model):
    """
    Tracks KPI metrics for CRO performance monitoring.
    Used by the AI engine to generate CRO scorecards.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cro = models.ForeignKey(CRO, on_delete=models.CASCADE, related_name="kpis")
    period_start = models.DateField()
    period_end = models.DateField()

    metric_name = models.CharField(
        max_length=100,
        help_text="e.g., 'site_activation_days', 'query_resolution_days', 'enrollment_rate_per_site_month'",
    )
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    actual_value = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=30, blank=True, default="", help_text="e.g., 'days', 'per_month', '%'")

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "clinical_cro_kpis"
        ordering = ["-period_end"]
        indexes = [
            models.Index(fields=["cro", "metric_name"]),
        ]

    def __str__(self):
        return f"{self.cro.name} - {self.metric_name}: {self.actual_value}/{self.target_value}"

    @property
    def on_target(self):
        """Check if actual meets target (assumes lower is better for time metrics)."""
        return self.actual_value <= self.target_value


# ---------------------------------------------------------------------------
# Clinical Trial & Site Management
# ---------------------------------------------------------------------------

class ClinicalTrial(models.Model):
    """
    Core clinical trial record. Links to a Plane project for task management.
    Tracks trial phase, enrollment, and key milestone dates.
    """

    class Phase(models.TextChoices):
        PHASE_I = "I", "Phase I"
        PHASE_I_II = "I/II", "Phase I/II"
        PHASE_II = "II", "Phase II"
        PHASE_II_III = "II/III", "Phase II/III"
        PHASE_III = "III", "Phase III"
        PHASE_IV = "IV", "Phase IV"

    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        IND_CTA_PREP = "ind_cta_prep", "IND/CTA Preparation"
        STARTUP = "startup", "Study Startup"
        ENROLLING = "enrolling", "Enrolling"
        FULLY_ENROLLED = "fully_enrolled", "Fully Enrolled"
        TREATMENT_COMPLETE = "treatment_complete", "Treatment Complete"
        DATA_LOCK = "data_lock", "Database Lock"
        ANALYSIS = "analysis", "Analysis"
        CSR_WRITING = "csr_writing", "CSR Writing"
        COMPLETED = "completed", "Completed"
        TERMINATED = "terminated", "Terminated"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    project_id = models.UUIDField(
        db_index=True,
        help_text="Links to a Plane project for task management",
    )

    protocol_number = models.CharField(max_length=100, unique=True)
    protocol_title = models.TextField(blank=True, default="")
    phase = models.CharField(max_length=10, choices=Phase.choices)
    indication = models.CharField(max_length=255)
    therapeutic_area = models.CharField(max_length=100, blank=True, default="")
    sponsor = models.CharField(max_length=255, blank=True, default="")
    compound_name = models.CharField(max_length=255, blank=True, default="")

    target_enrollment = models.IntegerField(default=0)
    current_enrollment = models.IntegerField(default=0)
    screen_failure_count = models.IntegerField(default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)

    # Key milestone dates
    protocol_finalized = models.DateField(null=True, blank=True)
    first_site_activated = models.DateField(null=True, blank=True)
    first_patient_in = models.DateField(null=True, blank=True)
    enrollment_50_pct = models.DateField(null=True, blank=True)
    last_patient_in = models.DateField(null=True, blank=True)
    last_patient_out = models.DateField(null=True, blank=True)
    database_lock = models.DateField(null=True, blank=True)
    csr_completion = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_trials"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.protocol_number} - {self.phase} ({self.status})"

    @property
    def enrollment_pct(self):
        if self.target_enrollment == 0:
            return 0
        return round(100 * self.current_enrollment / self.target_enrollment, 1)

    @property
    def screen_failure_rate(self):
        total_screened = self.current_enrollment + self.screen_failure_count
        if total_screened == 0:
            return 0
        return round(100 * self.screen_failure_count / total_screened, 1)


class TrialSite(models.Model):
    """
    Individual clinical trial site. Tracks IRB/EC approval, activation,
    enrollment, and which CRO manages the site.
    """

    class Status(models.TextChoices):
        IDENTIFIED = "identified", "Identified"
        FEASIBILITY = "feasibility", "Feasibility"
        SELECTED = "selected", "Selected"
        REGULATORY_PENDING = "regulatory_pending", "Regulatory Pending"
        IRB_EC_SUBMITTED = "irb_ec_submitted", "IRB/EC Submitted"
        IRB_EC_APPROVED = "irb_ec_approved", "IRB/EC Approved"
        ACTIVATED = "activated", "Activated"
        ENROLLING = "enrolling", "Enrolling"
        ENROLLMENT_COMPLETE = "enrollment_complete", "Enrollment Complete"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trial = models.ForeignKey(ClinicalTrial, on_delete=models.CASCADE, related_name="sites")
    cro = models.ForeignKey(
        CRO,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_sites",
        help_text="CRO responsible for managing this site",
    )

    site_number = models.CharField(max_length=50, blank=True, default="")
    site_name = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True, default="")
    country = models.CharField(max_length=5, help_text="ISO 3166-1 alpha-2")
    city = models.CharField(max_length=100, blank=True, default="")
    region = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="e.g., 'North America', 'Western Europe'",
    )

    principal_investigator = models.CharField(max_length=255)
    pi_email = models.EmailField(blank=True, default="")

    irb_ec_name = models.CharField(max_length=255, blank=True, default="")
    irb_ec_status = models.CharField(
        max_length=20,
        choices=[
            ("not_submitted", "Not Submitted"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("conditional", "Conditional Approval"),
            ("rejected", "Rejected"),
        ],
        default="not_submitted",
    )
    irb_ec_submission_date = models.DateField(null=True, blank=True)
    irb_ec_approval_date = models.DateField(null=True, blank=True)

    activation_date = models.DateField(null=True, blank=True)
    enrollment_target = models.IntegerField(default=0)
    enrollment_actual = models.IntegerField(default=0)
    screen_failure_count = models.IntegerField(default=0)

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.IDENTIFIED)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_trial_sites"
        ordering = ["country", "site_name"]
        indexes = [
            models.Index(fields=["trial", "country"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.site_name} ({self.country}) - PI: {self.principal_investigator}"

    @property
    def enrollment_pct(self):
        if self.enrollment_target == 0:
            return 0
        return round(100 * self.enrollment_actual / self.enrollment_target, 1)

    @property
    def screen_failure_rate(self):
        total = self.enrollment_actual + self.screen_failure_count
        if total == 0:
            return 0
        return round(100 * self.screen_failure_count / total, 1)


# ---------------------------------------------------------------------------
# Trial Master File (TMF)
# ---------------------------------------------------------------------------

class TMFDocument(models.Model):
    """
    Trial Master File document tracking per ICH E8.
    Maintains the essential document inventory required for regulatory inspection.
    """

    class Category(models.TextChoices):
        REGULATORY = "regulatory", "Regulatory"
        IRB_EC = "irb_ec", "IRB/Ethics Committee"
        PROTOCOL = "protocol", "Protocol"
        CONSENT = "consent", "Informed Consent"
        SAFETY = "safety", "Safety"
        MONITORING = "monitoring", "Monitoring"
        DATA_MANAGEMENT = "data_management", "Data Management"
        LABORATORY = "laboratory", "Laboratory"
        INVESTIGATOR = "investigator", "Investigator"
        SPONSOR = "sponsor", "Sponsor"
        STATISTICS = "statistics", "Statistics"
        CLOSE_OUT = "close_out", "Close-Out"

    class Status(models.TextChoices):
        MISSING = "missing", "Missing"
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Under Review"
        APPROVED = "approved", "Approved"
        SUPERSEDED = "superseded", "Superseded"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trial = models.ForeignKey(ClinicalTrial, on_delete=models.CASCADE, related_name="tmf_documents")
    site = models.ForeignKey(
        TrialSite,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tmf_documents",
        help_text="Null for trial-level documents, set for site-level documents",
    )

    category = models.CharField(max_length=20, choices=Category.choices)
    document_name = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=50,
        help_text="e.g., 'protocol', 'ib', 'icf', 'csr', 'sae_report', 'monitoring_report'",
    )
    version = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.MISSING)

    file_url = models.TextField(blank=True, default="")
    required = models.BooleanField(
        default=True,
        help_text="Is this an ICH E8 essential document?",
    )

    uploaded_by = models.UUIDField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinical_tmf_documents"
        ordering = ["category", "document_name"]
        indexes = [
            models.Index(fields=["trial", "category"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        site_label = f" ({self.site.site_name})" if self.site else ""
        return f"{self.document_name} v{self.version}{site_label} [{self.status}]"
