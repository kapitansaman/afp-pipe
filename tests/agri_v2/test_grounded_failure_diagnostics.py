import unittest
from automation.agri_v2.failure_diagnostics import failure_details
class GroundedFailureDiagnosticTests(unittest.TestCase):
 def test_fact_reference_error_is_actionable_not_unspecified(self):
  self.assertEqual(failure_details(ValueError('Exact owned approved fact references required')),{'kind':'validation','category':'unapproved_fact_reference'})
 def test_untrusted_provider_or_model_text_is_not_added_to_logs(self):
  self.assertEqual(failure_details(ValueError('untrusted arbitrary output or secret-value')),{'kind':'validation','category':'unspecified'})
