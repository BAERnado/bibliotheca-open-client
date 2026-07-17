"""HTTP client for bibliotheca-open.de."""

from dataclasses import dataclass
from urllib.parse import urlencode, urljoin, urlsplit

from aiohttp import ClientSession, ClientTimeout, CookieJar, FormData
from yarl import URL

from .models import Loan, RejectedRenewalProbe, RenewalResult
from .parser import (
    parse_bulk_renewal_controls,
    parse_direct_renewal_failure,
    parse_direct_renewal_target,
    parse_login_form,
    parse_loans,
    parse_postback_form,
    parse_renewal_query,
    parse_renewal_statuses,
)


_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) "
    "Gecko/20100101 Firefox/153.0"
)


@dataclass(frozen=True)
class FetchedPage:
    """An HTTP page returned by the library website."""

    url: str
    status: int
    html: str


@dataclass(frozen=True)
class LoginResult:
    """Login outcome together with the server reply for further analysis."""

    authenticated: bool
    page: FetchedPage
    login_reply: FetchedPage
    response_cookie_names: tuple[str, ...]
    session_cookie_names: tuple[str, ...]
    account_cookie_names: tuple[str, ...]


class BibliothecaClient:
    """Fetch bibliotheca-open pages without blocking the event loop."""

    def __init__(
        self,
        base_url: str,
        *,
        session: ClientSession | None = None,
        timeout: float = 30,
    ) -> None:
        parsed_url = urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed_url.username or parsed_url.password:
            raise ValueError("base_url must not contain credentials")

        self._base_url = base_url.rstrip("/") + "/"
        self._session = session
        self._owns_session = session is None
        self._timeout = ClientTimeout(total=timeout)

    async def __aenter__(self) -> "BibliothecaClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.async_close()

    async def _ensure_session(self) -> ClientSession:
        if self._session is None:
            # OPEN's legacy auth cookies must be sent byte-for-byte like a
            # browser; aiohttp's optional cookie quoting can invalidate them.
            self._session = ClientSession(
                cookie_jar=CookieJar(quote_cookie=False),
                timeout=self._timeout,
            )
        return self._session

    async def async_fetch_account_page(self, *, referer: str | None = None) -> FetchedPage:
        """Fetch the account page, following redirects and retaining cookies."""

        session = await self._ensure_session()
        url = urljoin(self._base_url, "Mein-Konto")
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.9,en;q=0.8",
            "User-Agent": _BROWSER_USER_AGENT,
        }
        if referer is not None:
            headers["Referer"] = referer
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            return FetchedPage(
                url=str(response.url),
                status=response.status,
                html=await response.text(),
            )

    async def async_login(self, username: str, password: str) -> LoginResult:
        """Submit the discovered WebForms login and return its response."""

        if not username or not password:
            raise ValueError("username and password must not be empty")

        initial_page = await self.async_fetch_account_page()
        session = await self._ensure_session()
        login_form = parse_login_form(initial_page.html, initial_page.url)
        if login_form is None:
            return LoginResult(
                authenticated=True,
                page=initial_page,
                login_reply=initial_page,
                response_cookie_names=(),
                session_cookie_names=tuple(
                    sorted(cookie.key for cookie in session.cookie_jar)
                ),
                account_cookie_names=tuple(
                    sorted(session.cookie_jar.filter_cookies(URL(initial_page.url)))
                ),
            )

        origin = f"{urlsplit(self._base_url).scheme}://{urlsplit(self._base_url).netloc}"
        headers = {
            "Accept": "*/*",
            "Accept-Language": "de,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Origin": origin,
            "Pragma": "no-cache",
            "Referer": self._base_url,
            "User-Agent": _BROWSER_USER_AGENT,
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
        }
        body = urlencode(login_form.payload(username, password)).encode("utf-8")
        async with session.post(
            login_form.action_url,
            data=body,
            headers=headers,
        ) as response:
            response.raise_for_status()
            response_cookie_names = tuple(sorted(response.cookies.keys()))
            login_reply = FetchedPage(
                url=str(response.url),
                status=response.status,
                html=await response.text(),
            )
        session_cookie_names = tuple(sorted(cookie.key for cookie in session.cookie_jar))
        account_url = urljoin(self._base_url, "Mein-Konto")
        account_cookie_names = tuple(
            sorted(session.cookie_jar.filter_cookies(URL(account_url)))
        )

        # The PageRequestManager returns a delta response, possibly containing a
        # client-side redirect. Fetching the account page again both follows that
        # intent and gives callers normal HTML to parse.
        page = await self.async_fetch_account_page(referer=initial_page.url)
        return LoginResult(
            authenticated=parse_login_form(page.html, page.url) is None,
            page=page,
            login_reply=login_reply,
            response_cookie_names=response_cookie_names,
            session_cookie_names=session_cookie_names,
            account_cookie_names=account_cookie_names,
        )

    async def async_fetch_loans(self, page: FetchedPage | None = None) -> tuple[Loan, ...]:
        """Load loans and their asynchronous renewal decisions."""

        page = page or await self.async_fetch_account_page()
        query = parse_renewal_query(page.html, page.url)
        if query is None or not query.copy_ids:
            return parse_loans(page.html)

        session = await self._ensure_session()
        payload = {
            "portalId": query.portal_id,
            "userName": query.user_name,
            "copyIds": ",".join(query.copy_ids),
            "culture": query.culture,
            "localResourceFile": query.local_resource_file,
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": page.url,
            "User-Agent": _BROWSER_USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }
        async with session.post(query.endpoint, json=payload, headers=headers) as response:
            response.raise_for_status()
            statuses = parse_renewal_statuses(await response.json())
        return parse_loans(page.html, statuses)

    async def async_probe_rejected_renewal(self, copy_id: str) -> RejectedRenewalProbe:
        """Probe WebForms reconstruction only for a freshly rejected loan.

        This intentionally calls OPEN's mutating direct-renewal endpoint, but
        refuses to do so unless the immediately preceding status response says
        the copy is not renewable.
        """

        page = await self.async_fetch_account_page()
        loans = await self.async_fetch_loans(page)
        loan = next((item for item in loans if item.copy_id == copy_id), None)
        if loan is None:
            raise ValueError("copy ID is not present in the current account")
        if loan.renewal is None:
            raise RuntimeError("renewal status is unavailable; refusing diagnostic POST")
        if loan.renewal.renewable:
            raise RuntimeError("copy is renewable; refusing diagnostic POST")

        target = parse_direct_renewal_target(page.html, copy_id)
        postback = parse_postback_form(page.html, page.url)
        form_data = FormData(default_to_multipart=True)
        for name, value in postback.payload(target):
            form_data.add_field(name, value)

        origin = f"{urlsplit(self._base_url).scheme}://{urlsplit(self._base_url).netloc}"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Origin": origin,
            "Pragma": "no-cache",
            "Referer": self._base_url,
            "User-Agent": _BROWSER_USER_AGENT,
        }
        session = await self._ensure_session()
        async with session.post(postback.action_url, data=form_data, headers=headers) as response:
            response.raise_for_status()
            response_page = FetchedPage(
                url=str(response.url),
                status=response.status,
                html=await response.text(),
            )

        message = parse_direct_renewal_failure(response_page.html)
        if message is None:
            raise RuntimeError("unexpected direct-renewal response; expected rejection missing")
        response_loans = parse_loans(response_page.html)
        response_loan = next((item for item in response_loans if item.copy_id == copy_id), None)
        return RejectedRenewalProbe(
            copy_id=copy_id,
            message=message,
            response_url=response_page.url,
            account_unchanged=(
                len(response_loans) == len(loans)
                and response_loan is not None
                and response_loan.due_date == loan.due_date
            ),
        )

    async def async_renew_loan(self, copy_id: str) -> RenewalResult:
        """Renew one loan through OPEN's checkbox submission."""

        page = await self.async_fetch_account_page()
        loans = await self.async_fetch_loans(page)
        loan = next((item for item in loans if item.copy_id == copy_id), None)
        if loan is None:
            raise ValueError("copy ID is not present in the current account")
        if loan.renewal is None or not loan.renewal.renewable:
            raise RuntimeError("copy is not currently renewable; refusing renewal")

        checkbox, submit, submit_value = parse_bulk_renewal_controls(page.html, copy_id)
        postback = parse_postback_form(page.html, page.url)
        form_data = FormData(default_to_multipart=True)
        for name, value in postback.checkbox_submission(checkbox, submit, submit_value):
            form_data.add_field(name, value)

        origin = f"{urlsplit(self._base_url).scheme}://{urlsplit(self._base_url).netloc}"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Origin": origin,
            "Pragma": "no-cache",
            "Referer": self._base_url,
            "User-Agent": _BROWSER_USER_AGENT,
        }
        session = await self._ensure_session()
        async with session.post(postback.action_url, data=form_data, headers=headers) as response:
            response.raise_for_status()
            response_page = FetchedPage(
                url=str(response.url),
                status=response.status,
                html=await response.text(),
            )

        error = parse_direct_renewal_failure(response_page.html)
        response_loans = parse_loans(response_page.html)
        response_loan = next((item for item in response_loans if item.copy_id == copy_id), None)
        renewed = response_loan is not None and response_loan.due_date != loan.due_date
        if not renewed and error is None:
            raise RuntimeError("unexpected renewal response")
        return RenewalResult(
            copy_id=copy_id,
            renewed=renewed,
            old_due_date=loan.due_date,
            new_due_date=response_loan.due_date if renewed else None,
            message=error,
            response_url=response_page.url,
            response_html=response_page.html,
        )

    async def async_close(self) -> None:
        """Close only sessions created by this client."""

        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
