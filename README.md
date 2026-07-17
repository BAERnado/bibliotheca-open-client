# bibliotheca-open-client

Async Python client and HTML parser for bibliotheca-open.de library accounts.
The project is currently an exploratory foundation. Its async ASP.NET AJAX
login is verified against the Kaltenkirchen installation; account parsing is
the next development stage.

## Inspect a public account page

Install the project into a virtual environment and invoke it as a module:

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m bibliotheca_open_client
```

The command fetches
`https://kaltenkirchen.bibliotheca-open.de/Mein-Konto`, detects its login form,
and prints the discovered field names. Use another installation with
`--base-url`.

To retain the fetched HTML for selector analysis:

```bash
.venv/bin/python -m bibliotheca_open_client --save-html
```

This writes `.debug/account.html` with permissions `0600`. Authenticated pages
can contain personal data and must not be committed or shared without careful
redaction; `.debug/` is ignored by Git.

For login diagnostics, the raw ASP.NET AJAX response is additionally written
next to the snapshot with `.login-reply.txt` appended to its stem.

## Test a login

Pass only the username on the command line; the password is requested without
echo and is never stored by the client:

```bash
.venv/bin/python -m bibliotheca_open_client \
  --username YOUR_LIBRARY_ID \
  --save-html .debug/account-authenticated.html
```

For local automation, `BIBLIOTHECA_USERNAME` and `BIBLIOTHECA_PASSWORD` are
also accepted. Environment variables can still be inspected by processes owned
by the same user, so the interactive password prompt is preferred.

The legacy OPEN authentication cookies must be sent without additional cookie
quoting. The client therefore owns a suitably configured `aiohttp.CookieJar`
unless a session is supplied by its caller.

## Check

```bash
.venv/bin/python -m unittest discover -s tests
```
