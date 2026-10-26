"""Deterministic same-site editorial links, separate from scientific citations."""
import html,re,urllib.parse,urllib.request
from html.parser import HTMLParser
from .queue import DATA,load_json
LINK_POLICY='agri-internal-links-v1';SITE='https://navar-abyari.ir'
def canonical(url):
 p=urllib.parse.urlsplit(url)
 if p.scheme!='https' or p.netloc!='navar-abyari.ir' or p.username or p.password or p.query:raise ValueError('Approved internal HTTPS destination required')
 return urllib.parse.unquote(p.path).rstrip('/') or '/'
def selected_links(topic,current_url,policy=None):
 policy=load_json(DATA/'internal-links.json') if policy is None else policy
 if policy.get('policy')!=LINK_POLICY:raise ValueError('Internal-link policy mismatch')
 current=canonical(current_url);text=str(topic.get('crop',''))+' '+str(topic.get('title',''));out=[]
 matrix=topic.get('commercial_matrix')
 if matrix is not None:
  from .content_matrix import links_enabled
  primary=policy['primary'] if links_enabled(matrix) else []
 else:primary=policy['primary']
 for row in primary+policy.get('related',[]):
  path=canonical(row['url'])
  if path==current:continue
  if row.get('match') and row['match'] not in text:continue
  if not isinstance(row.get('anchor'),str) or not row['anchor'].strip():raise ValueError('Internal anchor required')
  out.append(row)
 return out
class Anchors(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.active=None
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.active=[dict(attrs).get('href',''),'']
 def handle_data(self,text):
  if self.active is not None:self.active[1]+=text
 def handle_endtag(self,tag):
  if tag=='a' and self.active is not None:self.rows.append(tuple(self.active));self.active=None
def anchors(body):
 p=Anchors();p.feed(body);p.close();return p.rows
def norm(s):return re.sub(r'[\s\u200c]+','',s).replace('ي','ی').replace('ك','ک')
def contains_link(body,row):
 for href,text in anchors(body):
  try:same=canonical(href)==canonical(row['url'])
  except (ValueError,TypeError):continue
  if same and norm(text)==norm(row['anchor']):return True
 return False
def external_links(body):
 return [u for u,t in anchors(body) if urllib.parse.urlsplit(u).scheme in ('http','https') and urllib.parse.urlsplit(u).hostname!='navar-abyari.ir']
class LinkText(HTMLParser):
 def __init__(self,body,rows):
  super().__init__(convert_charrefs=False);self.rows=rows;self.done={r['anchor'] for r in rows if contains_link(body,r)};self.out=[];self.inside_anchor=0;self.in_p=0;self.blocked=0
 def handle_starttag(self,tag,attrs):
  self.out.append(self.get_starttag_text())
  if tag=='a':self.inside_anchor+=1
  if tag=='p':self.in_p+=1
  if tag in ('script','style','code','pre'):self.blocked+=1
 def handle_startendtag(self,tag,attrs):self.out.append(self.get_starttag_text())
 def handle_endtag(self,tag):
  self.out.append('</'+tag+'>')
  if tag=='a':self.inside_anchor=max(0,self.inside_anchor-1)
  if tag=='p':self.in_p=max(0,self.in_p-1)
  if tag in ('script','style','code','pre'):self.blocked=max(0,self.blocked-1)
 def handle_data(self,text):
  if self.in_p and not self.inside_anchor and not self.blocked:
   for row in self.rows:
    if row.get('kind')!='primary' or row['anchor'] in self.done:continue
    for alias in row.get('aliases',[row['anchor']]):
     pattern=r'(?<![\w\u200c])'+re.escape(alias)+r'(?![\w\u200c])'
     if re.search(pattern,text):
      text=re.sub(pattern,lambda m:'<a href="'+html.escape(row['url'],quote=True)+'">'+m.group(0)+'</a>',text,count=1);self.done.add(row['anchor']);break
  self.out.append(text)
 def handle_entityref(self,name):self.out.append('&'+name+';')
 def handle_charref(self,name):self.out.append('&#'+name+';')
 def handle_comment(self,text):self.out.append('<!--'+text+'-->')
 def handle_decl(self,text):self.out.append('<!'+text+'>')
def augment(body,topic,current_url,policy=None):
 rows=selected_links(topic,current_url,policy);parser=LinkText(body,rows);parser.feed(body);parser.close();result=''.join(parser.out)
 missing=[r for r in rows if r.get('kind')=='primary' and r['anchor'] not in parser.done]
 extras=[]
 if missing and topic.get('commercial_matrix'):
  extras.append('<p>برای بررسی گزینه‌های تجهیزات بخش آبیاری این موضوع، '+' و '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in missing)+' را ببینید. انتخاب محصول باید بر پایهٔ مشخصات واقعی مزرعه و شبکه انجام شود؛ این پیوند توصیهٔ یک مدل مشخص یا تضمین عملکرد نیست.</p>')
 elif missing:extras.append('<p>برای آشنایی با تجهیزات آبیاری مزرعه، '+' و '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in missing)+' را در همین سایت ببینید.</p>')
 related=[r for r in rows if r.get('kind')=='related' and not contains_link(result,r)]
 if related:extras.append('<p>مطالعهٔ مرتبط: '+'؛ '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in related[:2])+'.</p>')
 if extras:
  block='<!-- afp-internal-links:v1 -->'+''.join(extras)
  point=result.find('<h2>سؤالات متداول</h2>');result=result[:point]+block+result[point:] if point>=0 else result+block
 if external_links(result)!=external_links(body):raise ValueError('Scientific external citations changed')
 verify_links(result,rows);return result
def verify_links(body,rows):
 if any(not contains_link(body,row) for row in rows):raise ValueError('Required contextual internal link missing')
def validate_targets(rows):
 seen=set()
 for row in rows:
  url=row['url'];canonical(url)
  if url in seen:continue
  seen.add(url)
  req=urllib.request.Request(url,headers={'User-Agent':'AFP-internal-link-check'})
  with urllib.request.urlopen(req,timeout=45) as response:
   canonical(response.url)
   if response.status!=200 or canonical(response.url)!=canonical(url):raise ValueError('Internal destination is not the reviewed canonical page')
 return True
