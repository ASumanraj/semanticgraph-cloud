"""Models for Append-Only Audit Log (T-208).

Record authentication, authorization failures, admin changes, data access, export,
deletion, API-key lifecycle, and every LLM invocation — tenant, user, model,
version, token counts, scope.

The audit log is an immutable, append-only security and compliance substrate.
Content in the audit log inherits the same erasure obligations as the primary store,
which is why it holds IDs and cryptographic hashes rather than raw document text.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, Text
from sqlmodel import Field, SQLModel

from semanticgraph.domain.models.entities import TenantId

RETENTION_MONTHS: int = 15

FORBIDDEN_TEXT_KEYS: frozenset[str] = frozenset(
    {"text", "document_text", "content", "raw_content", "body", "document_body"}
)


class AuditEventType(StrEnum):
    """Categorized audit event types for security, compliance, and billing verification."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION_FAILURE = "authorization_failure"
    ADMIN_CHANGE = "admin_change"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    API_KEY_LIFECYCLE = "api_key_lifecycle"
    LLM_INVOCATION = "llm_invocation"


class AuditError(Exception):
    """Base exception for audit log operations."""


class DocumentTextNotAllowedError(AuditError, ValueError):
    """Raised when raw document text is passed into an audit event.

    Audit events must record identifiers and SHA-256 hashes only. Storing raw document
    text in audit logs violates telemetry data boundaries and GDPR erasure obligations.
    """


def hash_document_content(content: str | bytes) -> str:
    """Computes a canonical SHA-256 hash of document or data content.

    Returns the formatted digest as sha256:<64_hex_chars>.
    """
    raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
    digest = hashlib.sha256(raw_bytes).hexdigest()
    return f"sha256:{digest}"


def get_retention_cutoff(as_of: datetime | None = None) -> datetime:
    """Calculates the 15-month retention cutoff datetime.

    Covers a SOC 2 Type II audit window (12 months) plus a 3-month operational buffer.
    """
    if as_of is None:
        as_of = datetime.now(UTC)
    year = as_of.year
    month = as_of.month - RETENTION_MONTHS
    while month <= 0:
        month += 12
        year -= 1
    max_days = calendar.monthrange(year, month)[1]
    day = min(as_of.day, max_days)
    return as_of.replace(year=year, month=month, day=day)


def _assert_no_document_text(data: Any, key_name: str = "") -> None:
    """Recursively validates that no raw document text exists in audit event data."""
    if key_name.lower() in FORBIDDEN_TEXT_KEYS:
        raise DocumentTextNotAllowedError(
            f"Document text is not allowed in audit log. Key '{key_name}' is forbidden; "
            f"store references and SHA-256 hashes only."
        )
    if isinstance(data, dict):
        for k, v in data.items():
            _assert_no_document_text(v, str(k))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            _assert_no_document_text(item, key_name)
    elif isinstance(data, str) and len(data) > 500:
        raise DocumentTextNotAllowedError(
            "Document text is not allowed in audit log. String values exceeding 500 characters "
            "are prohibited; store document references and SHA-256 hashes only."
        )


@dataclass(frozen=True)
class AuditEvent:
    """An immutable, append-only security and compliance audit event."""

    tenant_id: TenantId
    event_id: UUID
    event_type: AuditEventType | str
    action: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_id: UUID | None = None
    actor_type: str = "user"
    resource_type: str | None = None
    resource_id: UUID | None = None
    scope: str | None = None
    data_hash: str | None = None
    model: str | None = None
    model_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        _assert_no_document_text(self.metadata)

        if self.event_type == AuditEventType.LLM_INVOCATION:
            if not self.model or not self.model_version:
                raise ValueError(
                    "model and model_version are required for llm_invocation audit events"
                )
            if self.input_tokens is not None and self.input_tokens < 0:
                raise ValueError(f"input_tokens must be non-negative, got {self.input_tokens}")
            if self.output_tokens is not None and self.output_tokens < 0:
                raise ValueError(f"output_tokens must be non-negative, got {self.output_tokens}")

    @property
    def user_id(self) -> UUID | None:
        """Alias for actor_id when actor is a user."""
        return self.actor_id

    def to_dict(self) -> dict[str, Any]:
        """Serializes the audit event into a standard dictionary for export."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id.value),
            "event_id": str(self.event_id),
            "event_type": str(self.event_type),
            "action": self.action,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "actor_type": self.actor_type,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "scope": self.scope,
            "data_hash": self.data_hash,
            "model": self.model,
            "model_version": self.model_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "metadata": self.metadata,
        }

    @classmethod
    def authentication(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.AUTHENTICATION,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def authorization_failure(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.AUTHORIZATION_FAILURE,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            resource_type=resource_type,
            resource_id=resource_id,
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def admin_change(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.ADMIN_CHANGE,
            action=action,
            actor_id=actor_id,
            actor_type="admin",
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def data_access(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        data_hash: str | None = None,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.DATA_ACCESS,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            resource_type=resource_type,
            resource_id=resource_id,
            data_hash=data_hash,
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def data_export(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.DATA_EXPORT,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            resource_type="export",
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def data_deletion(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        data_hash: str | None = None,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.DATA_DELETION,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            resource_type=resource_type,
            resource_id=resource_id,
            data_hash=data_hash,
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def api_key_lifecycle(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID | None,
        action: str,
        resource_id: UUID | None = None,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.API_KEY_LIFECYCLE,
            action=action,
            actor_id=actor_id,
            actor_type="user",
            resource_type="api_key",
            resource_id=resource_id,
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def llm_invocation(
        cls,
        tenant_id: TenantId,
        event_id: UUID,
        action: str,
        model: str,
        model_version: str,
        input_tokens: int,
        output_tokens: int,
        actor_id: UUID | None = None,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
        scope: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=AuditEventType.LLM_INVOCATION,
            action=action,
            actor_id=actor_id,
            actor_type="service",
            model=model,
            model_version=model_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            cache_write_input_tokens=cache_write_input_tokens,
            scope=scope,
            occurred_at=occurred_at or datetime.now(UTC),
            metadata=metadata or {},
        )


class SQLAuditEvent(SQLModel, table=True):
    """PostgreSQL storage model for the append-only audit event log."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_tenant_audit_occurred", "tenant_id", "occurred_at"),
        Index("idx_tenant_audit_event_id", "tenant_id", "event_id", unique=True),
        Index("idx_tenant_audit_type", "tenant_id", "event_type"),
        Index("idx_tenant_audit_recorded", "tenant_id", "recorded_at"),
        Index("idx_tenant_audit_actor", "tenant_id", "actor_id"),
        Index("idx_tenant_audit_resource", "tenant_id", "resource_type", "resource_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    event_id: UUID = Field(index=True, nullable=False)
    occurred_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    event_type: str = Field(nullable=False)
    action: str = Field(nullable=False)
    actor_id: UUID | None = Field(default=None, nullable=True)
    actor_type: str = Field(default="user", nullable=False)
    resource_type: str | None = Field(default=None, nullable=True)
    resource_id: UUID | None = Field(default=None, nullable=True)
    scope: str | None = Field(default=None, nullable=True)
    data_hash: str | None = Field(default=None, nullable=True)
    model: str | None = Field(default=None, nullable=True)
    model_version: str | None = Field(default=None, nullable=True)
    input_tokens: int | None = Field(default=None, sa_type=Integer, nullable=True)
    output_tokens: int | None = Field(default=None, sa_type=Integer, nullable=True)
    cache_read_input_tokens: int | None = Field(default=None, sa_type=Integer, nullable=True)
    cache_write_input_tokens: int | None = Field(default=None, sa_type=Integer, nullable=True)
    metadata_json: str | None = Field(default=None, sa_type=Text, nullable=True)

    def to_domain(self) -> AuditEvent:
        """Convert SQL row into domain AuditEvent."""
        meta = json.loads(self.metadata_json) if self.metadata_json else {}
        return AuditEvent(
            id=self.id,
            tenant_id=TenantId(self.tenant_id),
            event_id=self.event_id,
            occurred_at=self.occurred_at.replace(tzinfo=UTC)
            if not self.occurred_at.tzinfo
            else self.occurred_at,
            recorded_at=self.recorded_at.replace(tzinfo=UTC)
            if not self.recorded_at.tzinfo
            else self.recorded_at,
            event_type=self.event_type,
            action=self.action,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            scope=self.scope,
            data_hash=self.data_hash,
            model=self.model,
            model_version=self.model_version,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens,
            cache_write_input_tokens=self.cache_write_input_tokens,
            metadata=meta,
        )
