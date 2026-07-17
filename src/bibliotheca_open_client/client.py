"""HTTP client for bibliotheca-open.de."""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from aiohttp import ClientSession, ClientTimeout

from .parser import parse_login_form


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
            self._session = ClientSession(timeout=self._timeout)
        return self._session

    async def async_fetch_account_page(self) -> FetchedPage:
        """Fetch the account page, following redirects and retaining cookies."""

        session = await self._ensure_session()
        url = urljoin(self._base_url, "Mein-Konto")
        async with session.get(url) as response:
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
        login_form = parse_login_form(initial_page.html, initial_page.url)
        if login_form is None:
            return LoginResult(
                authenticated=True,
                page=initial_page,
                login_reply=initial_page,
            )

        session = await self._ensure_session()
        headers = {
            "Referer": initial_page.url,
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
        }
        async with session.post(
            login_form.action_url,
            data=login_form.payload(username, password),
            headers=headers,
        ) as response:
            response.raise_for_status()
            login_reply = FetchedPage(
                url=str(response.url),
                status=response.status,
                html=await response.text(),
            )

        # The PageRequestManager returns a delta response, possibly containing a
        # client-side redirect. Fetching the account page again both follows that
        # intent and gives callers normal HTML to parse.
        page = await self.async_fetch_account_page()
        return LoginResult(
            authenticated=parse_login_form(page.html, page.url) is None,
            page=page,
            login_reply=login_reply,
        )

    async def async_close(self) -> None:
        """Close only sessions created by this client."""

        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
