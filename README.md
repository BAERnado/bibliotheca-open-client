# bibliotheca-open-client

Async Python client and HTML parser for bibliotheca-open.de library accounts.
The project is currently an exploratory foundation; login and account parsing
are not implemented yet.

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

## Check

```bash
.venv/bin/python -m unittest discover -s tests
```
