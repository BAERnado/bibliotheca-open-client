"""HTML parsing for bibliotheca-open.de pages."""

from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Loan, RenewalStatus


# ponytail: an empty module ID is the generic /Login page; add a provider
# abstraction only if a genuinely different login form is observed.
_MODULE_ID = re.compile(r"^dnn_ctr(?P<module_id>\d*)_Login_Login_COP_txtUsername$")


@dataclass(frozen=True)
class LoginForm:
    """Fields needed to submit a discovered ASP.NET WebForms login."""

    action_url: str
    module_id: str
    username_field: str
    password_field: str
    submit_field: str
    submit_value: str
    hidden_fields: tuple[tuple[str, str], ...]
    auxiliary_fields: tuple[tuple[str, str], ...]

    def payload(self, username: str, password: str) -> tuple[tuple[str, str], ...]:
        """Build the ASP.NET AJAX POST observed from the browser."""

        update_panel = f"dnn$ctr{self.module_id}$Login_UP|{self.submit_field}"
        return (
            ("ScriptManager", update_panel),
            ("__EVENTTARGET", ""),
            ("__EVENTARGUMENT", ""),
        ) + self.hidden_fields + self.auxiliary_fields + (
            (self.username_field, username),
            (self.password_field, password),
            ("__ASYNCPOST", "true"),
            (self.submit_field, self.submit_value),
        )


@dataclass(frozen=True)
class RenewalQuery:
    """Parameters exposed by OPEN for its asynchronous renewal-status call."""

    endpoint: str
    portal_id: str
    user_name: str
    copy_ids: tuple[str, ...]
    culture: str
    local_resource_file: str


@dataclass(frozen=True)
class PostbackForm:
    """Successful controls from a WebForms form."""

    action_url: str
    fields: tuple[tuple[str, str], ...]

    def payload(self, event_target: str) -> tuple[tuple[str, str], ...]:
        found: set[str] = set()
        payload: list[tuple[str, str]] = []
        for name, value in self.fields:
            if name == "__EVENTTARGET":
                value = event_target
                found.add(name)
            elif name == "__EVENTARGUMENT":
                value = ""
                found.add(name)
            payload.append((name, value))
        if "__EVENTTARGET" not in found:
            payload.insert(0, ("__EVENTTARGET", event_target))
        if "__EVENTARGUMENT" not in found:
            payload.insert(1, ("__EVENTARGUMENT", ""))
        return tuple(payload)


def _field_name(element: Tag | None, description: str) -> str:
    if element is None or not isinstance(element.get("name"), str):
        raise ValueError(f"login form has no named {description} field")
    return element["name"]


def parse_login_form(html: str, page_url: str) -> LoginForm | None:
    """Find a COP login form without assuming a site-specific module number."""

    soup = BeautifulSoup(html, "html.parser")
    username = soup.find("input", id=_MODULE_ID)
    if not isinstance(username, Tag):
        return None

    match = _MODULE_ID.fullmatch(str(username.get("id")))
    if match is None:  # pragma: no cover - guaranteed by BeautifulSoup's filter
        return None
    module_id = match.group("module_id")

    form = username.find_parent("form")
    if not isinstance(form, Tag):
        raise ValueError("login fields are not contained in a form")

    prefix = f"dnn_ctr{module_id}_Login_Login_COP_"
    password = form.find("input", id=f"{prefix}txtPassword")
    submit = form.find("input", id=f"{prefix}cmdLogin")
    hidden_fields = tuple(
        (name, str(element.get("value", "")))
        for element in form.find_all("input", attrs={"type": "hidden"})
        if isinstance((name := element.get("name")), str)
    )
    search = form.find("input", id="dnn_dnnSEARCH_txtSearch")
    auxiliary_fields = (
        ((_field_name(search, "search"), str(search.get("value", ""))),)
        if isinstance(search, Tag)
        else ()
    )

    return LoginForm(
        action_url=urljoin(page_url, str(form.get("action", ""))),
        module_id=module_id,
        username_field=_field_name(username, "username"),
        password_field=_field_name(password if isinstance(password, Tag) else None, "password"),
        submit_field=_field_name(submit if isinstance(submit, Tag) else None, "submit"),
        submit_value=str(submit.get("value", "")) if isinstance(submit, Tag) else "",
        hidden_fields=hidden_fields,
        auxiliary_fields=auxiliary_fields,
    )


def _last_span_text(cell: Tag) -> str | None:
    spans = cell.find_all("span", recursive=False)
    text = spans[-1].get_text(" ", strip=True) if spans else cell.get_text(" ", strip=True)
    return text or None


def parse_loans(
    html: str,
    renewal_statuses: tuple[RenewalStatus, ...] = (),
) -> tuple[Loan, ...]:
    """Parse loan rows and merge separately loaded renewal decisions."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one('table[id$="grdViewLoans"]')
    if not isinstance(table, Tag):
        return ()

    statuses = {status.copy_id: status for status in renewal_statuses}
    rows = table.select(":scope > tbody > tr") or table.select(":scope > tr")
    loans: list[Loan] = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 7:
            continue
        copy_id_input = row.select_one('div.extendableRegion input[name$="CopyId"]')
        title_link = cells[2].find("a")
        if not isinstance(copy_id_input, Tag) or not isinstance(title_link, Tag):
            continue
        copy_id = str(copy_id_input.get("value", "")).strip()
        title = title_link.get_text(" ", strip=True)
        due_text = _last_span_text(cells[5])
        if not copy_id or not title or due_text is None:
            raise ValueError("loan row is missing copy ID, title, or due date")
        try:
            due_date = datetime.strptime(due_text, "%d.%m.%Y").date()
        except ValueError as error:
            raise ValueError(f"invalid loan due date: {due_text!r}") from error

        loans.append(
            Loan(
                copy_id=copy_id,
                title=title,
                author=_last_span_text(cells[3]),
                media_group=_last_span_text(cells[4]),
                due_date=due_date,
                renewal=statuses.get(copy_id),
            )
        )
    return tuple(loans)


def parse_renewal_query(html: str, page_url: str) -> RenewalQuery | None:
    """Extract the arguments used by OPEN's LoadExtensionsAsync call."""

    soup = BeautifulSoup(html, "html.parser")
    call_pattern = re.compile(
        r'LoadExtensionsAsync\("(?P<endpoint>[^"]+)",\s*"(?P<portal>\d+)",'
        r'\s*"(?P<resource>[^"]+)"\)'
    )
    match = call_pattern.search(html)
    user = soup.select_one('input[name$="PatronRndId"]')
    culture = soup.select_one('input[name$="Culture"]')
    copy_inputs = soup.select('div.extendableRegion input[name$="CopyId"]')
    if match is None or not isinstance(user, Tag) or not isinstance(culture, Tag):
        return None

    copy_ids = tuple(str(element.get("value", "")) for element in copy_inputs)
    return RenewalQuery(
        endpoint=urljoin(page_url, match.group("endpoint")),
        portal_id=match.group("portal"),
        user_name=str(user.get("value", "")),
        copy_ids=copy_ids,
        culture=str(culture.get("value", "")),
        local_resource_file=match.group("resource"),
    )


def parse_renewal_statuses(data: object) -> tuple[RenewalStatus, ...]:
    """Validate the JSON shape returned by IsCatalogueCopyExtendable."""

    if not isinstance(data, dict) or not isinstance(data.get("d"), list):
        raise ValueError("invalid renewal-status response")
    statuses: list[RenewalStatus] = []
    for item in data["d"]:
        if not isinstance(item, dict) or not isinstance(item.get("IsExtendable"), bool):
            raise ValueError("invalid renewal-status item")
        copy_id = item.get("CopyId")
        if not isinstance(copy_id, str) or not copy_id:
            raise ValueError("renewal-status item has no copy ID")
        statuses.append(
            RenewalStatus(
                copy_id=copy_id,
                renewable=item["IsExtendable"],
                reason=item.get("StatusMessages") or None,
                delay_text=item.get("DelayText") or None,
                extend_text=item.get("ExtendText") or None,
            )
        )
    return tuple(statuses)


def parse_postback_form(html: str, page_url: str) -> PostbackForm:
    """Collect enabled successful controls for a browser-like postback."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="Form")
    if not isinstance(form, Tag):
        raise ValueError("account page has no WebForms form")

    fields: list[tuple[str, str]] = []
    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name")
        if not isinstance(name, str) or element.has_attr("disabled"):
            continue
        if element.name == "input":
            input_type = str(element.get("type", "text")).lower()
            if input_type in {"button", "file", "reset", "submit"}:
                continue
            if input_type in {"checkbox", "radio"} and not element.has_attr("checked"):
                continue
            fields.append((name, str(element.get("value", "on"))))
        elif element.name == "textarea":
            fields.append((name, element.get_text()))
        else:
            selected = element.find_all("option", selected=True)
            if not selected:
                selected = element.find_all("option")[:1]
            fields.extend((name, str(option.get("value", option.get_text()))) for option in selected)

    return PostbackForm(
        action_url=urljoin(page_url, str(form.get("action", ""))),
        fields=tuple(fields),
    )


def parse_direct_renewal_target(html: str, copy_id: str) -> str:
    """Find the direct BtnExtendThis event target belonging to a copy ID."""

    soup = BeautifulSoup(html, "html.parser")
    copy_input = soup.find(
        "input",
        attrs={"name": re.compile(r"CopyId$")},
        value=copy_id,
    )
    row = copy_input.find_parent("tr") if isinstance(copy_input, Tag) else None
    link = row.select_one("a.oclc-patronaccountmodule-extendThis") if isinstance(row, Tag) else None
    href = str(link.get("href", "")) if isinstance(link, Tag) else ""
    match = re.search(r"__doPostBack\('([^']+)'\s*,\s*'[^']*'\)", href)
    if match is None:
        raise ValueError("loan has no direct renewal postback target")
    return match.group(1)


def parse_direct_renewal_failure(html: str) -> str | None:
    """Return OPEN's direct-renewal failure message, if present."""

    soup = BeautifulSoup(html, "html.parser")
    error = soup.select_one(
        'div[id$="extensionsPopup_divExtensionFailed"].dnnFormError[role="alert"]'
    )
    return error.get_text(" ", strip=True) or None if isinstance(error, Tag) else None
