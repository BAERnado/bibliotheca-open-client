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

## Renewal behavior

OPEN loads renewal decisions separately from the account HTML through
`IsCatalogueCopyExtendable`. A decision can be negative permanently or only in
the current situation. Preserve the server's reason text instead of inferring a
fixed category from localized wording.

Known cases include:

- media types excluded from renewal by the library;
- another renewal currently producing no later due date because the library
  calculates renewals from today instead of from the existing due date;
- overdue media, where the reason includes the accrued overdue amount. Overdue
  media cannot be renewed and must first be returned.

Each `Loan` exposes `overdue`, derived from whether its due date has passed.
Per-loan fees remain server-provided text; the account summary is represented
separately instead of guessing individual charges from localized messages.

`async_fetch_balance()` returns the fee summary as `AccountBalance`: open fees,
deposits, and total balance are represented as exact `Decimal` amounts with a
currency code. It returns `None` when an installation does not provide the
summary.

OPEN exposes two different renewal paths. A per-loan `BtnExtendThis` postback
attempts the renewal directly and is therefore a mutating operation. Do not use
it for previews or diagnostics. The checkbox-based `BtnExtendMediums` submit
also performs the renewal immediately; OPEN does not present a separate
confirmation step. Client code must never submit either mutating target as a
side effect of reading account data.

The guarded development command submits exactly one currently renewable
checkbox and changes the account:

```bash
.venv/bin/python -m bibliotheca_open_client \
  --username YOUR_LIBRARY_ID \
  --renew COPY_ID \
  --save-html .debug/renewal.html
```

The client refreshes the account and renewal status first and refuses the
request unless OPEN still marks that copy as renewable. The response is saved
separately with `.renewal.html` appended to the snapshot stem. A changed due
date is treated as success; OPEN's failure message is preserved otherwise.

For development only, a rejected direct-renewal postback can validate the
multipart WebForms reconstruction against a known nonrenewable copy:

```bash
.venv/bin/python -m bibliotheca_open_client \
  --username YOUR_LIBRARY_ID \
  --probe-rejected-renewal COPY_ID
```

This is deliberately labelled dangerous because `BtnExtendThis` is mutating.
The client refreshes the account and status immediately beforehand and refuses
the POST unless OPEN explicitly reports that copy as nonrenewable. Use it only
for a copy whose rejection is understood; it is not part of normal client use.

## Check

```bash
.venv/bin/python -m unittest discover -s tests
```

## Publish a release to PyPI

PyPI package names are global. First create accounts on
[PyPI](https://pypi.org/) and [TestPyPI](https://test.pypi.org/), enable 2FA,
and create a project-scoped API token when the project exists. Keep tokens out
of this repository and shell history.

Install the release tools in the virtual environment:

```bash
.venv/bin/pip install --upgrade build twine
```

Set the desired PEP 440 version in `pyproject.toml`, commit it, and tag the same
version. Build from a clean checkout and validate the artifacts:

Use a new output directory for every version so old artifacts cannot be
uploaded accidentally:

```bash
.venv/bin/python -m build --outdir dist/0.1.0
.venv/bin/python -m twine check dist/0.1.0/*
```

Upload to TestPyPI first. Use `__token__` as the username and enter the API
token when prompted:

```bash
.venv/bin/python -m twine upload --repository testpypi dist/0.1.0/*
```

Verify installation in a fresh virtual environment, then upload the unchanged
artifacts to production PyPI:

```bash
.venv/bin/python -m twine upload dist/0.1.0/*
```

Finally push the version commit and tag. PyPI releases cannot be replaced, so
any correction requires a new version. After publishing, keep the exact client
version in the Home Assistant integration's `manifest.json` synchronized.

## License

Copyright 2026 BAERnado. Licensed under the
[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution information.

## Development disclosure

This project was developed predominantly with AI-assisted *vibe coding*. The
project owner directed the requirements, supplied live observations, performed
functional tests, and reviewed parts of the source code, but did not manually
write or comprehensively audit every implementation detail. Users and
contributors should therefore review and test the code appropriately for their
own environment, especially before relying on account-changing operations such
as renewals.
