"""Normalize only source-bound citation tags in otherwise plain text fields."""
from html.parser import HTMLParser
from urllib.parse import urlsplit

def plain_citations(text,allowed_urls=None):
 if not isinstance(text,str):raise ValueError('Plain text field required')
 if '<' not in text and '>' not in text:return text,[]
 class Parser(HTMLParser):
  def __init__(self):super().__init__(convert_charrefs=True);self.text=[];self.urls=[];self.open=False
  def handle_starttag(self,tag,attrs):
   if tag!='a' or self.open or len(attrs)!=1 or attrs[0][0]!='href':raise ValueError('Unsafe markup in plain text field')
   url=attrs[0][1];p=urlsplit(url)
   if p.scheme!='https' or not p.hostname or p.username or p.password or (allowed_urls is not None and url not in allowed_urls):raise ValueError('Unapproved plain text citation')
   self.urls.append(url);self.open=True
  def handle_endtag(self,tag):
   if tag!='a' or not self.open:raise ValueError('Unsafe markup in plain text field')
   self.open=False
  def handle_data(self,text):self.text.append(text)
  def handle_comment(self,data):raise ValueError('Unsafe markup in plain text field')
  def handle_decl(self,decl):raise ValueError('Unsafe markup in plain text field')
 p=Parser();p.feed(text);p.close();visible=''.join(p.text)
 if p.open or '<' in visible or '>' in visible:raise ValueError('Unsafe markup in plain text field')
 return visible,p.urls
