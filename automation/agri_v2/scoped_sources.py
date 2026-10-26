"""Institutional HTML/PDF reads with per-hop HTTPS/public-DNS validation and bounded PDFs."""
import hashlib,ipaddress,io,socket,urllib.request,urllib.error,urllib.parse
from .research import source_host,ResearchBlocked,NoRedirect,Text,clean
from .queue import utcnow

def fetch(url):
 requested=url;chain=[];opener=urllib.request.build_opener(NoRedirect())
 for hop in range(5):
  host=source_host(url);addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
  if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):raise ResearchBlocked('non_public_source')
  if url in chain:raise ResearchBlocked('source_redirect_loop')
  chain.append(url)
  try:r=opener.open(urllib.request.Request(url,headers={'User-Agent':'AFP-scoped-evidence/1','Accept':'text/html,application/pdf'}),timeout=25)
  except urllib.error.HTTPError as e:
   code=e.code;location=e.headers.get('Location');e.close()
   if code not in (301,302,303,307,308) or not location:raise ResearchBlocked('scoped_source_http_'+str(code)) from None
   target=urllib.parse.urldefrag(urllib.parse.urljoin(url,location))[0];source_host(target)
   if hop==4:raise ResearchBlocked('source_redirect_limit')
   url=target;continue
  with r:
   mime=r.headers.get('Content-Type','').lower();blob=r.read(4_000_001)
   if r.status!=200 or len(blob)>4_000_000:raise ResearchBlocked('scoped_source_size_or_status')
   if 'application/pdf' in mime:
    if not blob.startswith(b'%PDF-'):raise ResearchBlocked('invalid_pdf_header')
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(blob),strict=True)
    if reader.is_encrypted or not 1<=len(reader.pages)<=40:raise ResearchBlocked('pdf_encryption_or_page_budget')
    parts=[];total=0
    for i,page in enumerate(reader.pages):
     if len(page.get_contents().get_data())>8_000_000:raise ResearchBlocked('pdf_page_stream_too_large')
     text=page.extract_text() or '';total+=len(text)
     if len(text)>80000 or total>200000:raise ResearchBlocked('pdf_text_budget')
     parts.append(' [page '+str(i+1)+'] '+text)
    text=clean(' '.join(parts));fmt='institutional_pdf_text';links=[]
   elif 'text/html' in mime:
    raw=blob.decode(r.headers.get_content_charset() or 'utf-8','replace');parser=Text();parser.feed(raw)
    from .source_tables import labelled_rows
    structured=labelled_rows(raw);text=clean(structured+' '+ ' '.join(parser.parts));fmt='institutional_html';links=[]
   else:raise ResearchBlocked('unsupported_scoped_source_type')
  if len(text)<500:raise ResearchBlocked('source_text_insufficient')
  truncated=len(text)>24000;text=text[:24000]
  return {'url':url,'requested_url':requested,'redirect_chain':chain,'text':text,'links':links,'fetched_at':utcnow(),'sha256':hashlib.sha256(text.encode()).hexdigest(),'source_format':fmt,'source_text_excerpted':truncated,'source_text_layout_version':2}
 raise ResearchBlocked('source_redirect_limit')
