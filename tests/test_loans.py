"""Regression checks for loans and asynchronous renewal decisions."""

from datetime import date
import unittest

from bibliotheca_open_client import RenewalStatus, parse_loans
from bibliotheca_open_client.parser import (
    parse_bulk_renewal_controls,
    parse_direct_renewal_failure,
    parse_direct_renewal_target,
    parse_postback_form,
    parse_renewal_confirmation,
    parse_renewal_statuses,
)


HTML = """
<form id="Form" action="/Mein-Konto">
<input type="hidden" name="__EVENTTARGET" value="">
<input type="hidden" name="__EVENTARGUMENT" value="old">
<input type="hidden" name="__dnnVariable" value="state">
<input type="submit" name="account$BtnExtendMediums" value="Renew selected">
<table id="dnn_ctr375_MainView_tpnlLoans_ucLoansView_grdViewLoans">
  <tr><th>Select</th><th>Cover</th><th>Title</th><th>Author</th>
      <th>Group</th><th>Due</th><th>Renewal</th></tr>
  <tr><td><div class="checkboxRegion">
        <input type="checkbox" name="row$chkSelect">
        <input type="hidden" name="row$CopyIdChx" value="copy-1">
      </div></td><td></td><td><a>Example title</a></td>
      <td><span>Author:</span><span>Example author</span></td>
      <td><span>Group:</span><span>Book</span></td>
      <td><span>Due:</span><span>31.08.2026</span></td>
      <td><div class="extendableRegion">
        <input type="hidden" name="row$CopyId" value="copy-1">
        <a class="oclc-patronaccountmodule-extendThis"
           href="javascript:__doPostBack('row$BtnExtendThis','')">Renew</a>
      </div></td></tr>
</table>
</form>
"""


class LoanTest(unittest.TestCase):
    def test_loan_with_temporary_nonrenewable_reason(self) -> None:
        statuses = parse_renewal_statuses(
            {
                "d": [
                    {
                        "CopyId": "copy-1",
                        "IsExtendable": False,
                        "StatusMessages": "The new due date may not precede the old one.",
                        "DelayText": "Try again later.",
                        "ExtendText": None,
                    }
                ]
            }
        )
        loans = parse_loans(HTML, statuses)

        self.assertEqual(1, len(loans))
        self.assertEqual(date(2026, 8, 31), loans[0].due_date)
        self.assertEqual("copy-1", loans[0].copy_id)
        self.assertEqual(
            RenewalStatus(
                copy_id="copy-1",
                renewable=False,
                reason="The new due date may not precede the old one.",
                delay_text="Try again later.",
            ),
            loans[0].renewal,
        )

    def test_direct_postback_reconstruction_and_failure(self) -> None:
        target = parse_direct_renewal_target(HTML, "copy-1")
        form = parse_postback_form(HTML, "https://example.test/Mein-Konto")

        self.assertEqual("row$BtnExtendThis", target)
        self.assertIn(("__EVENTTARGET", target), form.payload(target))
        self.assertIn(("__EVENTARGUMENT", ""), form.payload(target))
        self.assertIn(("__dnnVariable", "state"), form.payload(target))
        self.assertEqual(
            "Rejected",
            parse_direct_renewal_failure(
                '<div id="x_extensionsPopup_divExtensionFailed" '
                'class="dnnFormMessage dnnFormError" role="alert">'
                "<span>Rejected</span></div>"
            ),
        )

    def test_checkbox_preparation_and_confirmation(self) -> None:
        checkbox, submit, value = parse_bulk_renewal_controls(HTML, "copy-1")
        payload = parse_postback_form(
            HTML, "https://example.test/Mein-Konto"
        ).checkbox_submission(checkbox, submit, value)

        self.assertIn(("__EVENTTARGET", ""), payload)
        self.assertIn(("row$chkSelect", "on"), payload)
        self.assertIn(("account$BtnExtendMediums", "Renew selected"), payload)
        self.assertFalse(any(name.endswith("BtnExtendThis") for name, _ in payload))
        self.assertFalse(
            any(name.endswith("loansExtensionPopup$btnDefault") for name, _ in payload)
        )
        self.assertEqual(
            ("Please confirm", "1.50 EUR"),
            parse_renewal_confirmation(
                '<div id="x_loansExtensionPopup_popup" '
                'class="oclc-module-popup oclc-in-module-popup">'
                '<span id="x_LblConfirmMessage">Please confirm</span>'
                '<span id="x_LblFeeTotalData">1.50 EUR</span>'
                '<input name="x$loansExtensionPopup$btnDefault"></div>'
            ),
        )


if __name__ == "__main__":
    unittest.main()
