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

    @property
    def overdue(self) -> bool:
        """Whether the due date has passed in the client's local timezone."""

        return self.due_date < date.today()


@dataclass(frozen=True)
class RejectedRenewalProbe:
    """Expected rejection from a guarded direct-renewal diagnostic."""

    copy_id: str
    message: str
    response_url: str
    account_unchanged: bool


@dataclass(frozen=True)
class RenewalResult:
    """Outcome of requesting renewal for one loan."""

    copy_id: str
    renewed: bool
    old_due_date: date
    new_due_date: date | None
    message: str | None
    response_url: str
    response_html: str
