"""
Cheque auto-generation from rent + payment frequency (Dubai Leasing
Management Flow, Phase 3). Sits alongside the existing one-at-a-time
lease_cheque_view CRUD, which remains the edit/adjust surface -- this is
purely the bulk-convenience "generate the standard N cheques" action.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from utilities import constants


def _tenure_months(start_date, end_date):
    """Calendar months from start_date to end_date, counting any trailing
    partial month as a full one -- e.g. 01-Sep-2026 to 31-Aug-2028 is a
    full 24-month tenure, not 23 months + a few days."""
    delta = relativedelta(end_date + timedelta(days=1), start_date)
    months = delta.years * 12 + delta.months
    if delta.days > 0:
        months += 1
    return max(months, 1)


def generate_cheque_schedule(lease, frequency, start_date, created_by):
    """Compute and persist rent cheques (LeaseTransaction rows) for
    `lease`, one every (12 / N) months for N = PAYMENT_FREQUENCY_CHEQUE_COUNT
    (e.g. every 3 months for QUARTERLY), for as many periods as the
    lease's actual tenure (start_date -> lease.end_date) covers -- a
    2-year lease on quarterly payments gets 8 cheques, not a fixed 4.
    Each cheque's amount is lease.rent (monthly) x months covered, with
    the last cheque absorbing any rounding remainder so
    sum(amounts) == lease.rent * tenure_months exactly.

    Does NOT delete any existing cheques -- the caller
    (generate_cheque_schedule_view) decides regeneration policy.

    Raises ValueError if lease.rent or lease.end_date isn't set, or if
    `frequency` isn't a known PAYMENT_FREQUENCY_CHOICES value.
    """
    from lease.models import LeaseTransaction  # local import: avoid a
    # models<->this-module circular import at module load time.
    from user_service.models import DocumentType

    # LeaseTransaction extends Documents (MTI) -- document_type is a
    # required FK with no default, so a generic placeholder row is needed
    # here even though a plain rent cheque has no real uploaded document.
    doc_type, _ = DocumentType.objects.get_or_create(
        name=constants.RENT_CHEQUE, section=constants.LEASE_CHEQUE,
        defaults={"created_by": created_by},
    )

    monthly_rent = lease.rent
    if not monthly_rent:
        raise ValueError("Lease has no rent amount to schedule cheques from.")

    cheques_per_year = constants.PAYMENT_FREQUENCY_CHEQUE_COUNT.get(frequency)
    if not cheques_per_year:
        raise ValueError(f"Unknown payment frequency: {frequency!r}")
    month_step = 12 // cheques_per_year

    if not lease.end_date:
        raise ValueError("Lease has no end_date to compute the tenure from.")

    # lease.end_date is timezone-aware (loaded from the DB); start_date
    # comes in naive from _parse_date(). Strip tzinfo so date arithmetic
    # below doesn't raise on the naive/aware mismatch.
    lease_end_date = lease.end_date.replace(tzinfo=None)

    tenure_months = _tenure_months(start_date, lease_end_date)
    count = -(-tenure_months // month_step)  # ceil division -- a trailing
    # partial period still gets its own (smaller) cheque.

    total = round(monthly_rent * tenure_months, 2)
    amount_per_cheque = round(monthly_rent * month_step, 2)
    created = []

    for i in range(count):
        is_last = i == count - 1
        amount = round(total - amount_per_cheque * (count - 1), 2) if is_last else amount_per_cheque
        period_start = start_date + relativedelta(months=i * month_step)
        period_end = min(
            period_start + relativedelta(months=month_step, days=-1),
            lease_end_date,
        )
        transaction = LeaseTransaction.objects.create(
            lease=lease,
            document_type=doc_type,
            cheque_type=constants.RENT_CHEQUE,
            payment_type=constants.PAYMENT_TYPE_PDC,
            # Due date is always the 1st of the period's month, regardless
            # of which day of the month the lease itself starts on.
            cheque_date=period_start.replace(day=1),
            start_date=period_start,
            end_date=period_end,
            amount=amount,
            status=constants.CHEQUE_STATUS_BALANCE,
            created_by=created_by,
        )
        created.append(transaction)

    return created
