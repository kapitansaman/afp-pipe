import unittest
from unittest.mock import Mock,patch
from automation.agri_v2 import scoped_sources as s

class ScopedSourceTests(unittest.TestCase):
 def setup(self,mime,blob):
  r=Mock();r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False);r.status=200;from email.message import Message
  r.headers=Message();r.headers['Content-Type']=mime;r.read.return_value=blob;op=Mock();op.open.return_value=r;return op
 def test_html_is_sanitized_and_requested_url_bound(self):
  op=self.setup('text/html; charset=utf-8',('<script>evil</script><p>'+'Actual university source evidence '*40+'</p>').encode())
  with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(s.urllib.request,'build_opener',return_value=op):d=s.fetch('https://extension.psu.edu/beans')
  self.assertNotIn('evil',d['text']);self.assertEqual(d['source_format'],'institutional_html');self.assertEqual(d['requested_url'],d['redirect_chain'][0])
 def test_private_dns_is_rejected_before_network_request(self):
  op=Mock()
  with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]),patch.object(s.urllib.request,'build_opener',return_value=op),self.assertRaises(ValueError):s.fetch('https://extension.psu.edu/beans')
  op.open.assert_not_called()
 def test_non_institutional_and_unsupported_mime_rejected(self):
  with self.assertRaises(ValueError):s.fetch('https://untrusted.example/beans')
  op=self.setup('application/javascript',b'x'*800)
  with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(s.urllib.request,'build_opener',return_value=op),self.assertRaises(ValueError):s.fetch('https://extension.psu.edu/file')
 def test_pdf_is_text_only_and_page_count_bounded(self):
  op=self.setup('application/pdf',b'%PDF-1.5\n');page=Mock();page.get_contents.return_value.get_data.return_value=b'abc';page.extract_text.return_value='Actual PDF evidence with original crop and units. '*20;reader=Mock();reader.is_encrypted=False;reader.pages=[page]
  with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(s.urllib.request,'build_opener',return_value=op),patch('pypdf.PdfReader',return_value=reader):d=s.fetch('https://extension.psu.edu/a.pdf')
  self.assertEqual(d['source_format'],'institutional_pdf_text');self.assertIn('[page 1]',d['text'])
  reader.pages=[page]*41
  with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(s.urllib.request,'build_opener',return_value=op),patch('pypdf.PdfReader',return_value=reader),self.assertRaises(ValueError):s.fetch('https://extension.psu.edu/a.pdf')
 def test_pdf_header_or_encryption_never_accepted(self):
  for encrypted in (False,True):
   op=self.setup('application/pdf',b'%PDF-1.5\n' if encrypted else b'not pdf');reader=Mock();reader.is_encrypted=True
   with patch.object(s.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(s.urllib.request,'build_opener',return_value=op),patch('pypdf.PdfReader',return_value=reader),self.assertRaises(ValueError):s.fetch('https://extension.psu.edu/a.pdf')
