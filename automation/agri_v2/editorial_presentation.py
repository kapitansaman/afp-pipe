"""Reader-facing presentation only; approved article/evidence bytes are never rewritten."""
import html,re,urllib.parse
from html.parser import HTMLParser
from .internal_links import anchors,canonical,norm
VERSION='end-sources-related-language-v1'
START='<!-- afp-sources:end:v1 -->';END='<!-- /afp-sources:end:v1 -->'
LABELS={'fa-IR':'منابع','en-US':'Sources','ru-RU':'Источники','ar-IQ':'المصادر','tg-TJ':'Манбаъҳо'}
GENERIC={norm(x).lower() for x in ('منبع','منبع دانشگاهی','منبع ذخیره‌شده','منبع ترویجی','source','sources','university source','источник','манбаъ','المصدر')}
class SourceLinks(HTMLParser):
 def __init__(self,allowed):super().__init__(convert_charrefs=False);self.allowed=allowed;self.out=[];self.used=[];self.active=None
 def handle_starttag(self,tag,attrs):
  raw=self.get_starttag_text()
  if tag=='a':
   if self.active is not None:raise ValueError('Nested citation anchor')
   url=dict(attrs).get('href','');p=urllib.parse.urlsplit(url)
   if p.scheme in ('http','https') and p.hostname!='navar-abyari.ir':
    if url not in self.allowed:raise ValueError('Unapproved scientific source in presentation')
    self.active=[url,[],[]];return
  if self.active is not None:self.active[1].append(raw)
  else:self.out.append(raw)
 def handle_startendtag(self,tag,attrs):
  if self.active is not None:self.active[1].append(self.get_starttag_text())
  else:self.out.append(self.get_starttag_text())
 def handle_endtag(self,tag):
  if tag=='a' and self.active is not None:
   url,raw,text=self.active
   if url not in self.used:self.used.append(url)
   if norm(html.unescape(''.join(text))).strip(' []()،,.؛:').lower() not in GENERIC:self.out.extend(raw)
   self.active=None;return
  if self.active is not None:self.active[1].append('</'+tag+'>')
  else:self.out.append('</'+tag+'>')
 def handle_data(self,text):
  if self.active is not None:self.active[1].append(text);self.active[2].append(text)
  else:self.out.append(text)
 def handle_entityref(self,name):self.handle_data('&'+name+';')
 def handle_charref(self,name):self.handle_data('&#'+name+';')
 def handle_comment(self,text):
  if self.active is not None:self.active[1].append('<!--'+text+'-->')
  else:self.out.append('<!--'+text+'-->')
 def handle_decl(self,text):self.out.append('<!'+text+'>')

def end_sources(body,sources,language='fa-IR'):
 if language not in LABELS:raise ValueError('Unsupported bibliography language')
 by_url={s['url']:s for s in sources}
 if START in body:
  verify_sources(body,sources,language);return body
 parser=SourceLinks(by_url);parser.feed(body);parser.close()
 if parser.active is not None:raise ValueError('Unclosed source anchor')
 if not parser.used:raise ValueError('No actual approved citation to present')
 rows=[]
 for u in parser.used:
  s=by_url[u];label=s.get('title') or urllib.parse.urlsplit(u).hostname+' — '+urllib.parse.unquote(urllib.parse.urlsplit(u).path.rstrip('/').split('/')[-1]).replace('-',' ')
  rows.append('<li><a href="'+html.escape(u,quote=True)+'">'+html.escape(label)+'</a></li>')
 result=''.join(parser.out)+START+'<section class="afp-sources"><h2>'+LABELS[language]+'</h2><ul>'+''.join(rows)+'</ul></section>'+END
 verify_sources(result,sources,language);return result

def verify_sources(body,sources,language='fa-IR'):
 if body.count(START)!=1 or body.count(END)!=1 or not body.rstrip().endswith(END):raise ValueError('Sources must be the final post section')
 before,tail=body.split(START);block,after=tail.split(END)
 allowed={s['url'] for s in sources};external=lambda part:[u for u,t in anchors(part) if urllib.parse.urlsplit(u).scheme in ('https','http') and urllib.parse.urlsplit(u).hostname!='navar-abyari.ir']
 urls=external(block)
 if external(before) or not urls or len(set(urls))!=len(urls) or not set(urls)<=allowed or '<h2>'+LABELS[language]+'</h2>' not in block:raise ValueError('Invalid final scientific bibliography')
 return urls

def words(text):return re.sub(r'[^\w\s\u200c]',' ',html.unescape(text)).replace('ي','ی').replace('ك','ک').replace('\u200c',' ').split()
def related_articles(topic,current_url,records,language='fa-IR'):
 """Conservative exact crop/product match, not arbitrary same-site or commercial links."""
 if language!='fa-IR':raise ValueError('Translated relations require verified translation mapping')
 crop=words(topic.get('crop',''));title=words(topic.get('title',''));own=canonical(current_url)
 if not crop:return []
 phrase=' '+' '.join(crop)+' ';scored=[];seen=set()
 agricultural=set('کاشت برداشت آبیاری بذر خاک عملکرد هکتار کشت کود تغذیه آفات بیماری مزرعه سبز جوانه ریشه تنش'.split())
 for row in records:
  if row.get('status')!='publish' or type(row.get('id')) is not int:continue
  url=row.get('url','')
  try:path=canonical(url)
  except (ValueError,TypeError):continue
  text=html.unescape(str(row.get('title','')));tokens=words(text)
  if path==own or path in seen or row.get('language') not in (None,'','fa-IR') or not re.search('[\u0600-\u06ff]',text):continue
  if phrase not in ' '+' '.join(tokens)+' ' or not agricultural.intersection(tokens):continue
  shared=(set(title)-set(crop))&set(tokens);scored.append((len(shared),row['id'],{'kind':'related','anchor':text,'url':url,'post_id':row['id'],'language':'fa-IR'}));seen.add(path)
 return [r for score,ident,r in sorted(scored,key=lambda x:(-x[0],x[1]))[:2]]

def translated_related(wp,source_rows,language,current_url):
 """Only existing, published, same-language counterparts of relevant source articles."""
 rows=[]
 for related in source_rows:
  post,_=wp.call('posts/'+str(related['post_id'])+'?_fields=afp_translation_links')
  url=post.get('afp_translation_links',{}).get(language)
  if not url:continue
  try:
   if canonical(url)==canonical(current_url):continue
  except ValueError:continue
  slug=urllib.parse.urlsplit(url).path.rstrip('/').split('/')[-1]
  matches,_=wp.call('posts?slug='+urllib.parse.quote(slug)+'&status=publish&_fields=id,title,link,status,afp_language')
  valid=[p for p in matches if p.get('status')=='publish' and p.get('afp_language')==language and canonical(p['link'])==canonical(url)]
  if len(valid)!=1:continue
  p=valid[0];rows.append({'kind':'related','url':url,'anchor':html.unescape(p['title']['rendered']),'post_id':p['id'],'language':language})
 return rows
