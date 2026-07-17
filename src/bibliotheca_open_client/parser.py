"""HTML parsing for bibliotheca-open.de pages."""

from dataclasses import dataclass
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


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

    def payload(self, username: str, password: str) -> tuple[tuple[str, str], ...]:
        """Build the WebForms POST fields without discarding duplicate names."""

        return self.hidden_fields + (
            (self.username_field, username),
            (self.password_field, password),
            (self.submit_field, self.submit_value),
        )


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

    return LoginForm(
        action_url=urljoin(page_url, str(form.get("action", ""))),
        module_id=module_id,
        username_field=_field_name(username, "username"),
        password_field=_field_name(password if isinstance(password, Tag) else None, "password"),
        submit_field=_field_name(submit if isinstance(submit, Tag) else None, "submit"),
        submit_value=str(submit.get("value", "")) if isinstance(submit, Tag) else "",
        hidden_fields=hidden_fields,
    )
