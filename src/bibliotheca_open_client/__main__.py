"""Manual live inspection of a bibliotheca-open account page."""

import argparse
import asyncio
import os
from pathlib import Path

from .client import BibliothecaClient
from .parser import parse_login_form


DEFAULT_BASE_URL = "https://kaltenkirchen.bibliotheca-open.de"
DEFAULT_SNAPSHOT = Path(".debug/account.html")


def _save_private(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as snapshot:
        snapshot.write(content)


async def _run(base_url: str, snapshot: Path | None) -> None:
    async with BibliothecaClient(base_url) as client:
        page = await client.async_fetch_account_page()

    if snapshot is not None:
        _save_private(snapshot, page.html)
        print(f"Saved private HTML snapshot: {snapshot}")

    login_form = parse_login_form(page.html, page.url)
    print(f"Fetched: {page.url} ({page.status})")
    if login_form is None:
        print("No login form detected; the session may already be authenticated.")
        return

    print(f"Login module: ctr{login_form.module_id}")
    print(f"Form action: {login_form.action_url}")
    print(f"Username field: {login_form.username_field}")
    print(f"Password field: {login_form.password_field}")
    print(f"Submit field: {login_form.submit_field}")
    print(f"Hidden fields: {len(login_form.hidden_fields)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--save-html",
        nargs="?",
        const=DEFAULT_SNAPSHOT,
        type=Path,
        metavar="PATH",
        help="save potentially sensitive HTML (default: .debug/account.html)",
    )
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.base_url, arguments.save_html))


if __name__ == "__main__":
    main()
