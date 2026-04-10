"""
Compliance models for 21 CFR Part 11 / EU Annex 11 audit trail system.

Every data change in the system is captured in an immutable, hash-chained
audit log. Critical actions require electronic signatures (username + password
re-entry). All models here are designed to satisfy FDA and EMA inspection
requirements for computerized systems used in clinical trials.
"""

import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """
    Immutable audit trail record. Every create/update/delete across all
    regulated models is logged here automatically via AuditMiddleware.

    Implements 21 CFR Part 11 requirements:
    - Computer-generated timestamps (no manual override)
    - User identity tracking
    - Original data visibility (old_value preserved)
    - Chronological, permanent storage
    - Hash chain for tamper detection
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        APPROVE = "approve", "Approve"
        SIGN = "sign", "Sign"
        VIEW = "view", "View"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        PERMISSION_CHANGE = "permission_change", "Permission Change"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True, null=True, blank=True)
    user_id = models.UUIDField(db_index=True, null=True, blank=True)
    user_email = models.EmailField(blank=True, default="")
    user_display_name = models.CharField(max_length=255, blank=True, default="")

    action = models.CharField(max_length=20, choices=Action.choices)
    model_name = models.CharField(max_length=100, db_index=True)
    record_id = models.UUIDField(db_index=True, null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True, default="")
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    reason = models.TextField(
        blank=True,
        default="",
        help_text="Required for changes to regulatory records",
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # Hash chain for tamper detection (21 CFR Part 11 data integrity)
    previous_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 of the previous audit record in this workspace",
    )
    record_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 hash of this record's content",
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "compliance_audit_log"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["workspace_id", "created_at"]),
            models.Index(fields=["model_name", "record_id"]),
            models.Index(fields=["user_id", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.model_name}:{self.record_id} by {self.user_email} at {self.created_at}"

    def compute_hash(self):
        """Compute SHA-256 hash of this record's content for tamper detection."""
        content = (
            f"{self.id}{self.workspace_id}{self.user_id}{self.action}"
            f"{self.model_name}{self.record_id}{self.field_name}"
            f"{self.old_value}{self.new_value}{self.reason}"
            f"{self.previous_hash}{self.created_at.isoformat()}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if not self.record_hash:
            self.record_hash = self.compute_hash()
        super().save(*args, **kwargs)

    def verify_integrity(self):
        """Check that this record has not been tampered with."""
        return self.record_hash == self.compute_hash()


class ElectronicSignature(models.Model):
    """
    Electronic signature per 21 CFR Part 11 Subpart C.

    Requires authenticated user to re-enter credentials and state the
    meaning of the signature (e.g., 'Approved', 'Reviewed', 'Authorized').
    Linked to the audit log entry that triggered the signature.
    """

    class Meaning(models.TextChoices):
        APPROVED = "approved", "Approved"
        REVIEWED = "reviewed", "Reviewed"
        AUTHORIZED = "authorized", "Authorized"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_log = models.ForeignKey(
        AuditLog,
        on_delete=models.PROTECT,
        related_name="signatures",
    )
    user_id = models.UUIDField(db_index=True)
    user_email = models.EmailField()
    meaning = models.CharField(max_length=20, choices=Meaning.choices)
    signed_at = models.DateTimeField(default=timezone.now)
    signature_hash = models.CharField(
        max_length=64,
        help_text="SHA-256(user_id + meaning + signed_at + record content)",
    )

    class Meta:
        db_table = "compliance_electronic_signatures"
        ordering = ["signed_at"]

    def __str__(self):
        return f"{self.meaning} by {self.user_email} at {self.signed_at}"

    def compute_signature_hash(self):
        content = (
            f"{self.user_id}{self.meaning}{self.signed_at.isoformat()}"
            f"{self.audit_log.record_hash}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if not self.signature_hash:
            self.signature_hash = self.compute_signature_hash()
        super().save(*args, **kwargs)

    def verify(self):
        """Verify this signature has not been tampered with."""
        return self.signature_hash == self.compute_signature_hash()


class AccessControlLog(models.Model):
    """
    Tracks permission changes for role-based access control auditing.
    21 CFR Part 11 requires that access control changes are auditable.
    """

    class ChangeType(models.TextChoices):
        GRANT = "grant", "Grant"
        REVOKE = "revoke", "Revoke"
        MODIFY = "modify", "Modify"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    changed_by_user_id = models.UUIDField()
    affected_user_id = models.UUIDField()
    change_type = models.CharField(max_length=10, choices=ChangeType.choices)
    role_before = models.CharField(max_length=50, blank=True, default="")
    role_after = models.CharField(max_length=50, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "compliance_access_control_log"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.change_type} {self.affected_user_id} by {self.changed_by_user_id}"


class DataProcessingAgreement(models.Model):
    """
    Tracks GDPR Data Processing Agreement (DPA) status with each vendor/CRO.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SIGNED = "signed", "Signed"
        EXPIRED = "expired", "Expired"
        TERMINATED = "terminated", "Terminated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    vendor_name = models.CharField(max_length=255)
    vendor_type = models.CharField(max_length=50)  # 'cro', 'lab', 'technology', etc.
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    signed_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    document_url = models.TextField(blank=True, default="")
    data_categories = models.JSONField(
        default=list,
        help_text="Categories of personal data processed: ['patient_data', 'site_staff_data', etc.]",
    )
    legal_basis = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="GDPR Article 6 legal basis for processing",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compliance_data_processing_agreements"

    def __str__(self):
        return f"DPA: {self.vendor_name} ({self.status})"
