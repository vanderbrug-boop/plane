"""Serializers for compliance/audit trail API endpoints."""

from rest_framework import serializers

from .models import (
    AccessControlLog,
    AuditLog,
    DataProcessingAgreement,
    ElectronicSignature,
)


class AuditLogSerializer(serializers.ModelSerializer):
    signatures = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "workspace_id",
            "user_id",
            "user_email",
            "user_display_name",
            "action",
            "model_name",
            "record_id",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "ip_address",
            "record_hash",
            "created_at",
            "signatures",
        ]
        read_only_fields = fields

    def get_signatures(self, obj):
        sigs = obj.signatures.all()
        return ElectronicSignatureSerializer(sigs, many=True).data


class ElectronicSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicSignature
        fields = [
            "id",
            "user_id",
            "user_email",
            "meaning",
            "signed_at",
            "signature_hash",
        ]
        read_only_fields = fields


class AccessControlLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessControlLog
        fields = [
            "id",
            "workspace_id",
            "changed_by_user_id",
            "affected_user_id",
            "change_type",
            "role_before",
            "role_after",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class DataProcessingAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProcessingAgreement
        fields = [
            "id",
            "workspace_id",
            "vendor_name",
            "vendor_type",
            "status",
            "signed_date",
            "expiry_date",
            "document_url",
            "data_categories",
            "legal_basis",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
