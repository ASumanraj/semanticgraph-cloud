"""
Unit tests for domain bi-temporal modeling (T-203).

Acceptance Criteria tested:
- Facts carry both intervals (ValidInterval and TransactionInterval).
- Superseding a fact closes the prior validity window and leaves the entity in place.
- A query can evaluate the fact as it was believed at a past instant (transaction time)
  and as it was true in the world (valid time).
- A superseded fact is retrievable with its closed window.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.temporal.intervals import TransactionInterval, ValidInterval
from semanticgraph.domain.temporal.models import BiTemporalFact


class TestValidInterval:
    def test_valid_interval_open_by_default(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0)
        assert interval.valid_from == t0
        assert interval.valid_to is None
        assert interval.is_open is True

    def test_valid_interval_bounded(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        t1 = datetime(2023, 6, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0, valid_to=t1)
        assert interval.is_open is False
        assert interval.valid_to == t1

    def test_valid_interval_rejects_inverted_bounds(self) -> None:
        t0 = datetime(2023, 6, 1, tzinfo=UTC)
        t1 = datetime(2020, 1, 1, tzinfo=UTC)
        with pytest.raises(ValueError, match="valid_to cannot be earlier than valid_from"):
            ValidInterval(valid_from=t0, valid_to=t1)

    def test_valid_interval_contains(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        t1 = datetime(2023, 6, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0, valid_to=t1)

        # Before start
        assert not interval.contains(t0 - timedelta(seconds=1))
        # At start
        assert interval.contains(t0)
        # In between
        assert interval.contains(datetime(2021, 5, 1, tzinfo=UTC))
        # At end (half-open [start, end))
        assert not interval.contains(t1)
        # After end
        assert not interval.contains(t1 + timedelta(seconds=1))

    def test_valid_interval_open_contains_all_future(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0)
        assert interval.contains(t0)
        assert interval.contains(datetime(2099, 1, 1, tzinfo=UTC))
        assert not interval.contains(t0 - timedelta(seconds=1))

    def test_valid_interval_close(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0)
        closing_time = datetime(2023, 6, 1, tzinfo=UTC)

        closed = interval.close(closing_time)
        assert closed.valid_from == t0
        assert closed.valid_to == closing_time
        assert not closed.is_open
        # Original remains immutable
        assert interval.is_open

    def test_valid_interval_close_rejects_earlier_instant(self) -> None:
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        interval = ValidInterval(valid_from=t0)
        with pytest.raises(ValueError, match="Closing instant cannot be earlier than valid_from"):
            interval.close(t0 - timedelta(days=1))


class TestTransactionInterval:
    def test_transaction_interval_active_by_default(self) -> None:
        t0 = datetime(2020, 1, 5, 12, 0, 0, tzinfo=UTC)
        interval = TransactionInterval(created_at=t0)
        assert interval.created_at == t0
        assert interval.expired_at is None
        assert interval.is_active is True

    def test_transaction_interval_expired(self) -> None:
        t0 = datetime(2020, 1, 5, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2020, 2, 1, 12, 0, 0, tzinfo=UTC)
        interval = TransactionInterval(created_at=t0, expired_at=t1)
        assert interval.is_active is False
        assert interval.expired_at == t1

    def test_transaction_interval_rejects_inverted_bounds(self) -> None:
        t0 = datetime(2020, 2, 1, tzinfo=UTC)
        t1 = datetime(2020, 1, 1, tzinfo=UTC)
        with pytest.raises(ValueError, match="expired_at cannot be earlier than created_at"):
            TransactionInterval(created_at=t0, expired_at=t1)

    def test_transaction_interval_expire(self) -> None:
        t0 = datetime(2020, 1, 5, tzinfo=UTC)
        interval = TransactionInterval(created_at=t0)
        expiry = datetime(2020, 3, 1, tzinfo=UTC)

        expired = interval.expire(expiry)
        assert expired.created_at == t0
        assert expired.expired_at == expiry
        assert not expired.is_active
        # Immutable
        assert interval.is_active

    def test_transaction_interval_contains(self) -> None:
        t0 = datetime(2020, 1, 5, tzinfo=UTC)
        t1 = datetime(2020, 3, 1, tzinfo=UTC)
        interval = TransactionInterval(created_at=t0, expired_at=t1)

        assert not interval.contains(t0 - timedelta(seconds=1))
        assert interval.contains(t0)
        assert interval.contains(datetime(2020, 2, 1, tzinfo=UTC))
        assert not interval.contains(t1)


class TestBiTemporalFact:
    def test_fact_carries_both_intervals(self) -> None:
        tenant_id = TenantId(uuid4())
        v_start = datetime(2020, 1, 1, tzinfo=UTC)
        t_record = datetime(2020, 1, 5, tzinfo=UTC)

        fact = BiTemporalFact(
            tenant_id=tenant_id,
            claim="Acme CFO is Alice",
            valid_interval=ValidInterval(valid_from=v_start),
            transaction_interval=TransactionInterval(created_at=t_record),
            subject="Acme Corp",
            predicate="has_cfo",
            object="Alice",
        )

        assert fact.claim == "Acme CFO is Alice"
        assert fact.valid_interval.valid_from == v_start
        assert fact.valid_interval.valid_to is None
        assert fact.transaction_interval.created_at == t_record
        assert fact.transaction_interval.expired_at is None

    def test_superseding_fact_closes_prior_validity_window(self) -> None:
        tenant_id = TenantId(uuid4())
        t0_valid = datetime(2020, 1, 1, tzinfo=UTC)
        t0_system = datetime(2020, 1, 5, tzinfo=UTC)

        fact_a = BiTemporalFact(
            tenant_id=tenant_id,
            claim="Acme CFO is Alice",
            valid_interval=ValidInterval(valid_from=t0_valid),
            transaction_interval=TransactionInterval(created_at=t0_system),
            subject="Acme Corp",
            predicate="has_cfo",
            object="Alice",
        )

        # 2023: Bob becomes CFO
        t1_valid = datetime(2023, 6, 1, tzinfo=UTC)
        t1_system = datetime(2023, 6, 10, tzinfo=UTC)

        fact_b = BiTemporalFact(
            tenant_id=tenant_id,
            claim="Acme CFO is Bob",
            valid_interval=ValidInterval(valid_from=t1_valid),
            transaction_interval=TransactionInterval(created_at=t1_system),
            subject="Acme Corp",
            predicate="has_cfo",
            object="Bob",
        )

        # Supersede Fact A with Fact B
        superseded_a = fact_a.supersede(fact_b)

        # Fact A's prior validity window is closed at Fact B's valid_from
        assert superseded_a.valid_interval.valid_to == t1_valid
        assert superseded_a.superseded_by_id == fact_b.id
        # Row contents stay in place
        assert superseded_a.id == fact_a.id
        assert superseded_a.claim == "Acme CFO is Alice"
        assert superseded_a.subject == "Acme Corp"
        assert superseded_a.predicate == "has_cfo"
        assert superseded_a.object == "Alice"

    def test_as_of_valid_and_system_time_queries(self) -> None:
        tenant_id = TenantId(uuid4())
        t_valid_alice = datetime(2020, 1, 1, tzinfo=UTC)
        t_valid_bob = datetime(2023, 6, 1, tzinfo=UTC)

        t_sys_learned_alice = datetime(2020, 1, 5, tzinfo=UTC)
        t_sys_learned_bob = datetime(2023, 6, 10, tzinfo=UTC)

        fact_b = BiTemporalFact(
            tenant_id=tenant_id,
            claim="Acme CFO is Bob",
            valid_interval=ValidInterval(valid_from=t_valid_bob),
            transaction_interval=TransactionInterval(created_at=t_sys_learned_bob),
            subject="Acme Corp",
            predicate="has_cfo",
            object="Bob",
        )

        fact_a_open = BiTemporalFact(
            tenant_id=tenant_id,
            claim="Acme CFO is Alice",
            valid_interval=ValidInterval(valid_from=t_valid_alice),
            transaction_interval=TransactionInterval(created_at=t_sys_learned_alice),
            subject="Acme Corp",
            predicate="has_cfo",
            object="Alice",
        )
        fact_a_superseded = fact_a_open.supersede(fact_b)

        # 1. At 2021 (valid world time), who was CFO?
        t_query_2021 = datetime(2021, 6, 1, tzinfo=UTC)
        assert fact_a_superseded.is_valid_at(t_query_2021) is True
        assert fact_b.is_valid_at(t_query_2021) is False

        # 2. At 2024 (valid world time), who is CFO?
        t_query_2024 = datetime(2024, 1, 1, tzinfo=UTC)
        assert fact_a_superseded.is_valid_at(t_query_2024) is False
        assert fact_b.is_valid_at(t_query_2024) is True

        # 3. What did the system believe on 2021-01-01 (system time)?
        # At that instant, fact_b had not even been learned yet
        assert fact_a_superseded.was_believed_at(t_query_2021) is True
        assert fact_b.was_believed_at(t_query_2021) is False

        # 4. Bi-temporal slice check:
        # At world time 2021, believed at system time 2021 -> Alice matches!
        assert fact_a_superseded.as_of(valid_at=t_query_2021, system_at=t_query_2021) is True
        assert fact_b.as_of(valid_at=t_query_2021, system_at=t_query_2021) is False
