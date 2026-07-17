"""Manual live inspection of a bibliotheca-open account page."""

import argparse
import asyncio
import getpass
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


async def _run(
    base_url: str,
    snapshot: Path | None,
    username: str | None,
) -> None:
    login_reply = None
    async with BibliothecaClient(base_url) as client:
        if username is None:
            page = await client.async_fetch_account_page()
            authenticated = False
        else:
            password = os.environ.get("BIBLIOTHECA_PASSWORD") or getpass.getpass()
            result = await client.async_login(username, password)
            page = result.page
            authenticated = result.authenticated
            login_reply = result.login_reply

    if snapshot is not None:
        _save_private(snapshot, page.html)
        print(f"Saved private HTML snapshot: {snapshot}")
        if login_reply is not None and login_reply is not page:
            reply_path = snapshot.with_name(f"{snapshot.stem}.login-reply.txt")
            _save_private(reply_path, login_reply.html)
            print(f"Saved private login reply: {reply_path}")

    login_form = parse_login_form(page.html, page.url)
    print(f"Fetched: {page.url} ({page.status})")
    if username is not None:
        print(f"Authenticated: {'yes' if authenticated else 'no'}")
    if login_form is None:
        print("No login form detected.")
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
        "--username",
        default=os.environ.get("BIBLIOTHECA_USERNAME"),
        help="perform a login; defaults to BIBLIOTHECA_USERNAME",
    )
    parser.add_argument(
        "--save-html",
        nargs="?",
        const=DEFAULT_SNAPSHOT,
        type=Path,
        metavar="PATH",
        help="save potentially sensitive HTML (default: .debug/account.html)",
    )
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.base_url, arguments.save_html, arguments.username))


if __name__ == "__main__":
    main()
