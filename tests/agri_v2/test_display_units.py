import unittest
from automation.agri_v2.display_units import text,content,UnitReviewRequired
class DisplayUnitsTests(unittest.TestCase):
 def test_metric_temperature_for_all_non_english_locales(self):
  for lang in ['fa-IR','tg-TJ','ar-IQ','ru-RU']:self.assertEqual(text('68 °F',lang),'20 °C')
 def test_english_temperature_has_no_celsius_parenthesis(self):self.assertEqual(text('20 °C','en-US'),'68 °F')
 def test_us_units_with_metric_parenthesis(self):self.assertEqual(text('1 m','en-US'),'3.281 ft (1 m)')
 def test_feet_to_meters(self):self.assertEqual(text('5 feet','fa-IR'),'1.524 m')
 def test_area_is_not_converted_as_length(self):self.assertEqual(text('100 m²','en-US'),'1076.391 ft² (100 m²)')
 def test_yield_ratio_uses_area_conversion_too(self):self.assertEqual(text('100 lb/acre','fa-IR'),'112.085 kg/ha')
 def test_temperature_range_converts_both_endpoints(self):self.assertEqual(text('50–68 °F','fa-IR'),'10–20 °C')
 def test_negative_temperature(self):self.assertEqual(text('-40 °F','fa-IR'),'-40 °C')
 def test_temperature_difference_has_no_absolute_offset(self):self.assertEqual(text('difference 9 °F','fa-IR'),'difference 5 °C')
 def test_dual_temperature_is_not_duplicated(self):self.assertEqual(text('20 °C (68 °F)','en-US'),'68 °F')
 def test_unqualified_gallons_not_guessed(self):
  with self.assertRaises(UnitReviewRequired):text('10 gallons','fa-IR')
 def test_thermal_accumulation_not_misread_as_absolute_temperature(self):
  with self.assertRaises(UnitReviewRequired):text('100 degree-days','fa-IR')
 def test_href_attributes_never_change(self):self.assertEqual(content('<a href="https://example.edu/68°F">68 °F</a>','fa-IR'),'<a href="https://example.edu/68°F">20 °C</a>')
 def test_html_entities_do_not_split_measurement(self):self.assertEqual(content('<p>68&nbsp;°F &lt; limit</p>','fa-IR'),'<p>20 °C &lt; limit</p>')
 def test_persian_digits(self):self.assertEqual(text('۶۸ درجه فارنهایت','fa-IR'),'20 °C')
 def test_uncertainty_and_geography_not_changed(self):self.assertEqual(text('may reach 68 °F in Idaho','fa-IR'),'may reach 20 °C in Idaho')
 def test_plain_urls_are_unchanged(self):self.assertEqual(text('https://example.edu/68°F','fa-IR'),'https://example.edu/68°F')
 def test_mass_metric_parenthesis(self):self.assertEqual(text('1 kg','en-US'),'2.205 lb (1 kg)')
 def test_unknown_locale_is_not_guessed(self):
  with self.assertRaises(UnitReviewRequired):text('1 m','unknown')
 def test_unsupported_compound_not_converted_as_simple_length(self):
  with self.assertRaises(UnitReviewRequired):text('10 mm/day','en-US')
 def test_supported_yield_ratio_is_allowed(self):self.assertEqual(text('100 kg/ha','en-US'),'89.218 lb/acre (100 kg/ha)')
 def test_fraction_not_misread_as_integer_quantity(self):
  with self.assertRaises(UnitReviewRequired):text('1/2 inch','fa-IR')
 def test_ambiguous_comma_measurement_is_not_guessed(self):
  with self.assertRaises(UnitReviewRequired):text('1,500 ft','fa-IR')
 def test_thermal_rate_not_converted_with_absolute_offset(self):
  with self.assertRaises(UnitReviewRequired):text('5 °F/hour','fa-IR')
 def test_postfixed_temperature_difference(self):self.assertEqual(text('9 °F warmer','fa-IR'),'5 °C warmer')
 def test_english_body_and_faq_use_same_policy(self):
  from automation.agri_v2.multilingual import localized_body
  row={'language':'en-US','title':'Test','content_html':'<p>20 °C and 1 m <a href="https://example.edu/source">Source</a></p>','faq':[{'question':'Temperature?','answer':'20 °C'}]};body=localized_body(row,[{'id':1,'url':'https://example.com/image.webp'}],{'en-US':[]});self.assertNotIn('°C',body);self.assertIn('68 °F',body);self.assertIn('3.281 ft (1 m)',body)

 def test_persian_times_is_not_misread_as_bar_pressure(self):self.assertEqual(text('3 بار آبیاری','fa-IR'),'3 بار آبیاری')
 def test_english_preposition_in_is_not_misread_as_inches(self):self.assertEqual(text('3 in 10 seeds','en-US'),'3 in 10 seeds')
 def test_explicit_bar_pressure_still_converts(self):self.assertEqual(text('3 bar','fa-IR'),'300 kPa')
