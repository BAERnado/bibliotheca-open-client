"""Small regression check for dynamic bibliotheca login module IDs."""

import unittest

from bibliotheca_open_client import parse_login_form


HTML = """
<form method="post" action="/Mein-Konto">
  <input type="hidden" name="__VIEWSTATE" value="state">
  <input type="hidden" name="__EVENTVALIDATION" value="validation">
  <input id="dnn_ctr362_Login_Login_COP_txtUsername"
         name="dnn$ctr362$Login$Login_COP$txtUsername">
  <input id="dnn_ctr362_Login_Login_COP_txtPassword"
         name="dnn$ctr362$Login$Login_COP$txtPassword" type="password">
  <input id="dnn_ctr362_Login_Login_COP_cmdLogin"
         name="dnn$ctr362$Login$Login_COP$cmdLogin" type="submit">
</form>
"""


class LoginFormTest(unittest.TestCase):
    def test_dynamic_module_id_and_webforms_fields(self) -> None:
        form = parse_login_form(HTML, "https://example.test/Mein-Konto")

        self.assertIsNotNone(form)
        assert form is not None
        self.assertEqual("362", form.module_id)
        self.assertEqual("https://example.test/Mein-Konto", form.action_url)
        self.assertEqual(
            "dnn$ctr362$Login$Login_COP$txtUsername", form.username_field
        )
        self.assertEqual(
            (("__VIEWSTATE", "state"), ("__EVENTVALIDATION", "validation")),
            form.hidden_fields,
        )
        self.assertEqual(
            (
                (
                    "ScriptManager",
                    "dnn$ctr362$Login_UP|dnn$ctr362$Login$Login_COP$cmdLogin",
                ),
                ("__EVENTTARGET", ""),
                ("__EVENTARGUMENT", ""),
                ("__VIEWSTATE", "state"),
                ("__EVENTVALIDATION", "validation"),
                ("dnn$ctr362$Login$Login_COP$txtUsername", "reader"),
                ("dnn$ctr362$Login$Login_COP$txtPassword", "päss&=+%"),
                ("__ASYNCPOST", "true"),
                ("dnn$ctr362$Login$Login_COP$cmdLogin", ""),
            ),
            form.payload("reader", "päss&=+%"),
        )

    def test_generic_login_page_without_module_number(self) -> None:
        form = parse_login_form(
            HTML.replace("ctr362", "ctr"),
            "https://example.test/Login?loggedoff=err",
        )

        self.assertIsNotNone(form)
        assert form is not None
        self.assertEqual("", form.module_id)
        self.assertEqual("dnn$ctr$Login$Login_COP$txtPassword", form.password_field)


if __name__ == "__main__":
    unittest.main()
