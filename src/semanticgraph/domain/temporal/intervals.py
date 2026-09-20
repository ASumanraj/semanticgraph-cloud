"""
Time intervals for bi-temporal domain modeling.

Enforces:
- Valid time interval (when a fact was true in the real world).
- Transaction time interval (when the system recorded / believed the fact).
- Half-open interval semantics [start, end) consistent with ISO SQL:2011 and temporal databases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def _ensure_utc(dt: datetime, param_name: str) -> datetime:
    if dt.tzinfo is None:
        raise ValueError(f"{param_name} must be timezone-aware (UTC)")
    return dt.astimezone(UTC)


@dataclass(frozen=True)
class ValidInterval:
    """Represents the real-world valid time of a fact [valid_from, valid_to).

    If valid_to is None, the fact is currently valid (open-ended).
    """

    valid_from: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        vf = _ensure_utc(self.valid_from, "valid_from")
        object.__setattr__(self, "valid_from", vf)

        if self.valid_to is not None:
            vt = _ensure_utc(self.valid_to, "valid_to")
            if vt < vf:
                raise ValueError("valid_to cannot be earlier than valid_from")
            object.__setattr__(self, "valid_to", vt)

    @property
    def is_open(self) -> bool:
        """True if the valid time interval is open-ended into the future."""
        return self.valid_to is None

    def contains(self, instant: datetime) -> bool:
        """Returns True if the instant falls within [valid_from, valid_to)."""
        inst = _ensure_utc(instant, "instant")
        if inst < self.valid_from:
            return False
        return self.valid_to is None or inst < self.valid_to

    def close(self, closing_instant: datetime) -> ValidInterval:
        """Closes the interval at closing_instant, returning an immutable new instance."""
        inst = _ensure_utc(closing_instant, "closing_instant")
        if inst < self.valid_from:
            raise ValueError("Closing instant cannot be earlier than valid_from")
        return ValidInterval(valid_from=self.valid_from, valid_to=inst)


@dataclass(frozen=True)
class TransactionInterval:
    """Represents the system belief / recording time of a fact [created_at, expired_at).

    If expired_at is None, the system currently believes the fact.
    """

    created_at: datetime
    expired_at: datetime | None = None

    def __post_init__(self) -> None:
        ca = _ensure_utc(self.created_at, "created_at")
        object.__setattr__(self, "created_at", ca)

        if self.expired_at is not None:
            ea = _ensure_utc(self.expired_at, "expired_at")
            if ea < ca:
                raise ValueError("expired_at cannot be earlier than created_at")
            object.__setattr__(self, "expired_at", ea)

    @property
    def is_active(self) -> bool:
        """True if the system currently believes this fact (unexpired)."""
        return self.expired_at is None

    def contains(self, instant: datetime) -> bool:
        """Returns True if the instant falls within [created_at, expired_at)."""
        inst = _ensure_utc(instant, "instant")
        if inst < self.created_at:
            return False
        return self.expired_at is None or inst < self.expired_at

    def expire(self, expiry_instant: datetime) -> TransactionInterval:
        """Expires the fact in system time at expiry_instant."""
        inst = _ensure_utc(expiry_instant, "expiry_instant")
        if inst < self.created_at:
            raise ValueError("Expiry instant cannot be earlier than created_at")
        return TransactionInterval(created_at=self.created_at, expired_at=inst)
