"""HTTP client for bibliotheca-open.de."""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from aiohttp import ClientSession, ClientTimeout


@dataclass(frozen=True)
class FetchedPage:
    """An HTTP page returned by the library website."""

    url: str
    status: int
    html: str


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

    async def async_close(self) -> None:
        """Close only sessions created by this client."""

        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
