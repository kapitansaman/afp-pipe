import unittest
from automation.agri_v2.source_tables import labelled_rows
class SourceTableTests(unittest.TestCase):
 def test_simple_table_preserves_parameter_and_measurement(self):
  out=labelled_rows('<table><tr><th>Parameters</th><th>Measurements</th></tr><tr><td>Plant population per acre</td><td>3,630–4,356</td></tr></table>');self.assertIn('Plant population per acre | Measurements: 3,630–4,356',out)
 def test_complex_spans_do_not_create_inferred_headers(self):
  self.assertEqual(labelled_rows('<table><tr><th colspan="2">Yield</th></tr><tr><td>pumpkin</td><td>38.5</td></tr></table>'),'')
 def test_missing_columns_are_not_misassigned(self):
  self.assertEqual(labelled_rows('<table><tr><th>Crop</th><th>Yield</th><th>Unit</th></tr><tr><td>pumpkin</td><td>38.5</td></tr></table>'),'')
