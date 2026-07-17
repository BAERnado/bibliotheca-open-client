"""Public account models."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RenewalStatus:
    """Current renewal decision returned by OPEN."""

    copy_id: str
    renewable: bool
    reason: str | None = None
    delay_text: str | None = None
    extend_text: str | None = None


@dataclass(frozen=True)
class Loan:
    """A checked-out library medium."""

    copy_id: str
    title: str
    author: str | None
    media_group: str | None
    due_date: date
    renewal: RenewalStatus | None


@dataclass(frozen=True)
class RejectedRenewalProbe:
    """Expected rejection from a guarded direct-renewal diagnostic."""

    copy_id: str
    message: str
    response_url: str
    account_unchanged: bool
