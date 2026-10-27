"""Practical direct-HTML writing; repair inert formatting, never invent or approve facts."""
import html,json,re
from html.parser import HTMLParser
from .pipeline import article_prompt,normalize_article,validate_article,validate_for_publication,digest,numbers
from .queue import atomic_json

class Visible(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.paragraphs=[];self.current=None
 def handle_starttag(self,tag,attrs):
  if tag=='p':self.current=[]
 def handle_endtag(self,tag):
  if tag=='p' and self.current is not None:self.paragraphs.append(''.join(self.current).strip());self.current=None
 def handle_data(self,text):
  self.parts.append(text)
  if self.current is not None:self.current.append(text)

class Balanced(HTMLParser):
 def __init__(self):super().__init__();self.stack=[]
 def handle_starttag(self,tag,attrs):
  if tag!='br':self.stack.append(tag)
 def handle_endtag(self,tag):
  if tag=='br':return
  if not self.stack or self.stack.pop()!=tag:raise ValueError('Irreparable article HTML nesting')

def unwrap(raw):
 """Choose exactly one article object. Never pick among conflicting alternatives."""
 if not isinstance(raw,dict):raise ValueError('Article JSON object required')
 def candidate(row):return isinstance(row,dict) and ('content_html' in row or 'html' in row)
 found=[]
 def visit(row,path,depth):
  if not isinstance(row,dict) or depth>2:return
  if candidate(row):found.append((path,row))
  for key in ('article','result','data','schema','content'):
   if isinstance(row.get(key),dict):visit(row[key],path+[key],depth+1)
 visit(raw,[],0)
 if len(found)!=1:raise ValueError('Ambiguous or missing article object')
 return found[0]

def normalize(raw,topic,brief):
 path,row=unwrap(raw);fixes=[]
 if path:fixes.append({'kind':'unwrap_inert_object','path':path})
 if 'content_html' in row and 'html' in row and row['content_html']!=row['html']:raise ValueError('Conflicting article HTML fields')
 body=row.get('content_html',row.get('html'))
 if not isinstance(body,str):raise ValueError('Article HTML required')
 if 'content_html' not in row:fixes.append({'kind':'html_field_alias'})
 fenced=re.fullmatch(r'\s*```(?:html)?\s*\n(.*?)\n```\s*',body,re.S|re.I)
 if fenced:body=fenced[1];fixes.append({'kind':'strip_inert_html_fence'})
 title=row.get('title',topic['title'])
 if title!=topic['title']:raise ValueError('Generated title changed canonical intent')
 if 'title' not in row:fixes.append({'kind':'restore_canonical_title'})
 if 'faq' in row and 'faqs' in row and row['faq']!=row['faqs']:raise ValueError('Conflicting FAQ fields')
 faq=row.get('faq',row.get('faqs'))
 if 'faq' not in row and 'faqs' in row:fixes.append({'kind':'faq_field_alias'})
 article={'title':title,'content_html':body,'excerpt':row.get('excerpt'),'faq':faq}
 article=normalize_article(article,brief)
 if article['content_html']!=body:fixes.append({'kind':'normalize_inert_html'})
 balance=Balanced();balance.feed(article['content_html']);balance.close()
 if balance.stack:
  article['content_html']+=''.join('</'+tag+'>' for tag in reversed(balance.stack));fixes.append({'kind':'close_unclosed_inert_tags_at_end'})
 parser=Visible();parser.feed(article['content_html']);parser.close()
 if article['excerpt'] in (None,''):
  text=next((p for p in parser.paragraphs if len(p)>=20),'')
  excerpt=text[:450].rsplit(' ',1)[0] if len(text)>450 else text
  if len(excerpt)<20:raise ValueError('Excerpt cannot be derived from existing prose')
  article['excerpt']=excerpt;fixes.append({'kind':'copy_excerpt_from_existing_paragraph'})
 seen=set()
 for paragraph in parser.paragraphs:
  key=' '.join(paragraph.split())
  if len(key)>=80 and key in seen:raise ValueError('Duplicate substantive article paragraph')
  seen.add(key)
 approved=' '.join(f.get('claim','')+' '+f.get('conditions','') for f in brief['approved_facts'])
 if isinstance(article['excerpt'],str) and numbers(article['excerpt'])-numbers(approved):raise ValueError('Unapproved numeric token in draft')
 from .content_matrix import attach
 article=attach(article,topic,brief);article['writing_policy']='practical-direct-html-v1';validate_article(article,topic,brief);validate_for_publication(article)
 visible=' '.join(parser.parts)+' '+' '.join(f['question']+' '+f['answer'] for f in article['faq']);style_warnings=[]
 if len(visible.split())<550:style_warnings.append({'kind':'overall_length_below_editorial_target_not_blocker','words':len(visible.split()),'editorial_target':550})
 return article,{'version':1,'strategy':'practical-direct-html-v1','raw_sha256':digest(raw),'article_sha256':digest(article),'format_repairs':fixes,'warnings':style_warnings+[{'kind':'short_paragraph_is_not_a_blocker','words':len(p.split())} for p in parser.paragraphs if p and len(p.split())<50],'final_independent_evidence_review_required':True,'claims_added_by_normalizer':False}

def generate(client,topic,brief,folder):
 request=json.loads(article_prompt(topic,brief));request.pop('constraints',None)
 request['task']+=' Return the article object DIRECTLY at the root with title, content_html, excerpt and faq. HTML prose is the output, not a nested schema or fact-ID outline. There is NO required section count, paragraph count, per-paragraph word limit or per-paragraph fact-ID field. Use natural short and long paragraphs. Do not repeat scope caveats or pad text to meet length. Put source limits where needed and once in a concise limits section. Cite approved source URLs on the relevant claims. Exactly three FAQs.'
 atomic_json(folder/'practical-text-contract.json',{'strategy':'practical-direct-html-v1','response_format':'json_object','paragraph_length_hard_gate':False,'fixed_section_count':False,'per_paragraph_fact_ids_required':False,'final_evidence_audit_required':True})
 raw=client.text(json.dumps(request,ensure_ascii=False),attempts=1,max_tokens=14000,timeout=180)
 atomic_json(folder/'practical-text-candidate.json',raw)
 article,report=normalize(raw,topic,brief);atomic_json(folder/'practical-text-normalization.json',report);return article
