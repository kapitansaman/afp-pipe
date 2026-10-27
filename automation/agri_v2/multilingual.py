"""Four bounded translations from final Persian; immutable shared-media publication."""
import concurrent.futures,hashlib,html,json,re,urllib.parse,urllib.request
from html.parser import HTMLParser
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .pipeline import numbers,digest
from .client import ModelClient
LANGUAGES=('ru-RU','ar-IQ','tg-TJ','en-US')
LABELS={'ru-RU':'Russian','ar-IQ':'clear professional Arabic for Iraqi readers','tg-TJ':'Tajik in Cyrillic, not Persian script','en-US':'English'}
PHRASES={'ru-RU':'Оборудование для орошения','ar-IQ':'معدات الري','tg-TJ':'Таҷҳизоти обёрӣ','en-US':'Irrigation equipment'}
FAQ_LABEL={'ru-RU':'Часто задаваемые вопросы','ar-IQ':'الأسئلة الشائعة','tg-TJ':'Саволҳои маъмул','en-US':'Frequently asked questions'}
DISCLOSURES={'ru-RU':'Материал подготовлен с помощью ИИ и университетских источников и не заменяет оценку местного специалиста.','ar-IQ':'أُعد هذا المقال بمساعدة الذكاء الاصطناعي ومصادر جامعية ولا يغني عن تقييم ظروف الحقل واستشارة مختص محلي.','tg-TJ':'Ин мақола бо ёрии зеҳни сунъӣ ва манбаъҳои донишгоҳӣ омода шудааст ва ҷойгузини арзёбии шароити маҳаллӣ нест.','en-US':'Prepared with AI assistance and university sources; not a substitute for local field assessment and professional advice.'}
class Segments(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.texts=[];self.unwrapped=[]
 def handle_starttag(self,tag,attrs):
  from .pipeline import SafeHTML
  if tag not in SafeHTML.ALLOWED:raise ValueError('Unsupported translation HTML')
  attrs=dict(attrs)
  if tag=='a':
   u=attrs.get('href','');p=urllib.parse.urlsplit(u)
   if p.hostname=='navar-abyari.ir':self.unwrapped.append(True);return
   if p.scheme!='https' or not p.hostname or set(attrs)!={'href'}:raise ValueError('Unsafe source citation')
   self.unwrapped.append(False);self.parts.append('<a href="'+html.escape(u,quote=True)+'">');return
  if attrs:raise ValueError('Unexpected source attribute')
  self.parts.append('<'+tag+'>')
 def handle_endtag(self,tag):
  if tag=='a' and self.unwrapped.pop():return
  self.parts.append('</'+tag+'>')
 def handle_data(self,text):
  if text.strip():self.parts.append(len(self.texts));self.texts.append(text)
  else:self.parts.append(text)
 def handle_comment(self,data):raise ValueError('Unexpected source comment')
 def render(self,values):return ''.join(html.escape(values[p],quote=False) if isinstance(p,int) else p for p in self.parts)
def source_segments(article):
 parser=Segments();parser.feed(article['content_html']);parser.close()
 values=parser.texts+[article['title'],article['excerpt']]+[f[k] for f in article['faq'] for k in ('question','answer')]
 return parser,values

def validate_rows(result,values,lang):
 rows=result.get('translations') if isinstance(result,dict) else None
 if not isinstance(rows,list) or len(rows)!=len(values):raise ValueError('Translation segment count mismatch')
 if any(not isinstance(r,dict) or type(r.get('id')) is not int for r in rows):raise ValueError('Invalid translation IDs')
 mapping={r['id']:r.get('text') for r in rows}
 if len(mapping)!=len(values) or set(mapping)!=set(range(len(values))):raise ValueError('Translation IDs changed')
 translated=[mapping[i] for i in range(len(values))]
 for source,target in zip(values,translated):
  if not isinstance(target,str) or not target.strip() or re.search(r'[<>\u3400-\u9fff]',target):raise ValueError('Unsafe translated text')
  from .text_fields import plain_citations
  source_plain,_=plain_citations(source)
  if numbers(source_plain)!=numbers(target):raise ValueError('Translation changed numbers')
 text=' '.join(translated)
 script=r'[А-Яа-яЁёҚқҒғҲҳҶҷӢӣӮӯ]' if lang in ('ru-RU','tg-TJ') else (r'[ء-ي]' if lang=='ar-IQ' else r'[A-Za-z]')
 if len(re.findall(script,text))<100:raise ValueError('Wrong translation script')
 if lang in ('ru-RU','tg-TJ','en-US') and re.search(r'[\u0600-\u06ff]',text):raise ValueError('Persian/Arabic residue in translation')
 return translated

def render_translation(article,result,lang):
 parser,values=source_segments(article);translated=validate_rows(result,values,lang);n=len(parser.texts)
 row={'language':lang,'title':translated[n],'excerpt':translated[n+1],'content_html':parser.render(translated),'faq':[{'question':translated[n+2+i*2],'answer':translated[n+3+i*2]} for i in range(3)],'source_article_sha256':digest(article)}
 if article.get('commercial_matrix',{}).get('crop')=='هویج':
  expected={'ru-RU':r'морков','ar-IQ':r'جزر','tg-TJ':r'сабзӣ|сабзи','en-US':r'carrot'}[lang]
  if not re.search(expected,row['title'],re.I):raise ValueError('Translation crop identity changed')
  if lang=='tg-TJ' and 'ҷуворимакка' in str(row).lower() and 'ذرت' not in str(article):raise ValueError('Translation crop identity changed')
 return row
class TranslationClient(ModelClient):
 def request(self,kind,path,payload,timeout,attempts=None):return super().request(kind,path,payload,timeout,attempts=1)

def translate_one(article,lang,folder,health,client_factory=TranslationClient):
 path=folder/'translations'/f'{lang}.json';receipt=path.with_suffix('.receipt.json')
 if path.exists():
  row=load_json(path)
  if row.get('source_article_sha256')!=digest(article):raise ValueError('Translation source changed')
  return row
 if receipt.exists():raise ValueError('Translation attempt already consumed')
 atomic_json(receipt,{'status':'reserved','at':utcnow(),'max_calls':1,'source_article_sha256':digest(article)})
 parser,values=source_segments(article)
 try:
  from .translation_chunks import translate_segments
  result=translate_segments(client_factory(health,allow_calls=True),article,lang,folder)
  atomic_json(path.with_suffix('.raw.json'),result);row=render_translation(article,result,lang);atomic_json(path,row);atomic_json(receipt,{'status':'validated','at':utcnow(),'max_calls':1,'source_article_sha256':digest(article)});return row
 except Exception:
  atomic_json(receipt,{'status':'needs_review','at':utcnow(),'max_calls':1,'source_article_sha256':digest(article)});raise

def start(article,folder,health):
 cfg=load_json(DATA/'config.json').get('multilingual',{})
 if not cfg.get('enabled'):return None
 if cfg.get('independent_publication'):
  from .language_review_queue import handoff
  from .queue import get_topic
  handoff(get_topic('new',folder.name),article,folder);return None
 from .recovery import circuit_open
 if circuit_open('text'):return None
 pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
 futures={lang:pool.submit(translate_one,article,lang,folder,health) for lang in LANGUAGES}
 return pool,futures

def finish(job,folder):
 if job is None:return
 pool,futures=job;states={}
 for lang,future in futures.items():
  try:future.result();states[lang]='validated'
  except Exception:states[lang]='needs_review'
 pool.shutdown(wait=True);atomic_json(folder/'translations'/'status.json',{'at':utcnow(),'languages':states,'shared_images':True,'new_image_calls':0})

def verify_target(url,lang,fetcher=None):
 from .internal_links import canonical
 canonical(url)
 if fetcher is None:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AFP-language-link-check'}),timeout=30) as r:
   final=r.url;body=r.read(2_000_000).decode('utf-8','replace');status=r.status
 else:final,body,status=fetcher(url)
 if canonical(final)!=canonical(url) or status!=200:raise ValueError('Unverified localized target')
 m=re.search(r'<html\b[^>]*\blang=[\"\x27]([^\"\x27]+)',body,re.I)
 if not m or m[1].lower()!=lang.lower():raise ValueError('Internal target language mismatch')
 return True

def localized_body(row,media,policy,fetcher=None):
 lang=row['language'];body=row['content_html'];rows=policy[lang]
 # All in-site links must come from an explicit verified same-language map.
 from .internal_links import anchors
 if any(urllib.parse.urlsplit(u).hostname=='navar-abyari.ir' for u,t in anchors(body)):raise ValueError('Unmapped in-site link in translation')
 for target in rows:verify_target(target['url'],lang,fetcher)
 if rows:body+='<p>'+PHRASES[lang]+': '+' · '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in rows)+'</p>'
 matches=list(re.finditer('<h2>',body));at=matches[len(matches)//2].start() if len(matches)>1 else len(body)
 body=body[:at]+'<figure class="wp-block-image"><img src="'+html.escape(media[1]['url'],quote=True)+'" alt="'+html.escape(row['title'],quote=True)+'" loading="lazy"/></figure>'+body[at:]
 body+='<p><em>'+DISCLOSURES[lang]+'</em></p><h2>'+FAQ_LABEL[lang]+'</h2><div class="faq-section">'+''.join('<details><summary>'+html.escape(f['question'])+'</summary><p>'+html.escape(f['answer'])+'</p></details>' for f in row['faq'])+'</div>'
 return body

def publish_family(wp,folder,topic,source_result):
 from .internal_links import anchors
 folder=__import__('pathlib').Path(folder);cfg=load_json(DATA/'config.json').get('multilingual',{})
 if not cfg.get('enabled'):return source_result
 if cfg.get('independent_publication'):
  from .language_review_queue import handoff
  handoff(topic,load_json(folder/'article.json'),folder)
 status=folder/'translations'/'publication-status.json'
 schema,_=wp.call('posts',method='OPTIONS');properties=schema.get('schema',{}).get('properties',{})
 if not {'afp_language','afp_source_post_id'}<=properties.keys():
  atomic_json(status,{'status':'pending_wordpress_language_bridge','at':utcnow(),'source_post_id':source_result['post_id'],'languages':list(LANGUAGES)})
  return dict(source_result,translations_status='pending_wordpress_language_bridge')
 source_receipt=load_json(folder/'wordpress-receipt.json');media=sorted(source_receipt['media'],key=lambda m:m['index'])
 if len(media)!=2 or len({m['id'] for m in media})!=2:raise ValueError('Exactly two shared source media required')
 policy=load_json(DATA/'internal-links-i18n.json')['languages'];done={}
 article=load_json(folder/'article.json')
 if 'commercial_matrix' in article:
  from .content_matrix import links_enabled
  if not links_enabled(article['commercial_matrix']):policy={lang:[] for lang in policy}
 related_labels={'ru-RU':'Связанная статья','ar-IQ':'مقال ذو صلة','tg-TJ':'Мақолаи марбут','en-US':'Related article'}
 for related in load_json(DATA/'internal-links.json').get('related',[]):
  if related.get('match') and related['match'] not in str(topic.get('crop',''))+' '+str(topic.get('title','')):continue
  if not related.get('post_id'):continue
  original,_=wp.call('posts/'+str(related['post_id'])+'?_fields=afp_translation_links')
  for lang,url in original.get('afp_translation_links',{}).items():
   if lang in LANGUAGES:policy[lang].append({'anchor':related_labels[lang],'url':url})
 for lang in LANGUAGES:
  try:
   from .language_review_queue import enabled as independent,approved as language_approved,path as review_state,publication_due
   split=independent(DATA)
   if split and load_json(review_state(folder,lang)).get('status')=='published' and language_approved(folder,article,lang):
    done[lang]=load_json(folder/'translations'/(lang+'.wordpress.json'));continue
   if split and (not language_approved(folder,article,lang) or not publication_due(load_json(review_state(folder,lang)))):
    done[lang]={'status':'pending_separate_review'};continue
   pp=folder/'translations'/f'{lang}.json'
   if not pp.exists():done[lang]={'status':'translation_pending'};continue
   row=load_json(pp)
   if row['source_article_sha256']!=digest(load_json(folder/'article.json')):raise ValueError('Translated source changed')
   rp=folder/'translations'/f'{lang}.wordpress.json';slug=load_json(folder/'wordpress-draft-payload.json')['slug']+'-'+lang.lower()
   marker='<!-- afp-agri-v2:'+topic['id']+':'+lang+' -->'
   content=localized_body(row,media,policy)
   matches=[]
   if rp.exists():
    known=load_json(rp);post,_=wp.call('posts/'+str(known['post_id'])+'?context=edit');matches=[post]
    if post.get('slug')!=slug:raise ValueError('Receipt slug changed')
   else:
    for state in ('publish','draft','pending','future','private'):
     found,_=wp.call('posts?slug='+slug+'&status='+state+'&context=edit');matches+=found
   if len(matches)>1:raise ValueError('Ambiguous translated slug')
   if matches:
    post=matches[0]
    if post['author']!=wp.user_id or marker not in post['content']['raw']:raise ValueError('Translation not owned')
    if post['status'] not in ('draft','publish'):raise ValueError('Translation status changed')
   else:
    if rp.exists():raise ValueError('Translation receipt missing remote post')
    post,_=wp.call('posts','POST',{'title':row['title'],'slug':slug,'content':marker+'\n'+content,'excerpt':row['excerpt'],'featured_media':media[0]['id'],'status':'draft','comment_status':'closed','ping_status':'closed','afp_language':lang,'afp_source_post_id':source_result['post_id']})
    atomic_json(rp,{'post_id':post['id'],'status':'draft','shared_media':media})
   post,_=wp.call('posts/'+str(post['id'])+'?context=edit')
   if post.get('afp_language')!=lang or post.get('afp_source_post_id')!=source_result['post_id'] or post.get('featured_media')!=media[0]['id']:raise ValueError('Translation language/media registration failed')
   rendered=post['content'].get('rendered','')
   if media[1]['url'] not in rendered:raise ValueError('Shared inline image missing')
   for u,text in anchors(rendered):
    if urllib.parse.urlsplit(u).hostname=='navar-abyari.ir':verify_target(u,lang)
   if post['status']=='draft':post,_=wp.call('posts/'+str(post['id']),'POST',{'status':'publish'})
   verify_target(post['link'],lang)
   final,_=wp.call('posts/'+str(post['id']))
   if final.get('status')!='publish' or final.get('afp_language')!=lang or html.unescape(final.get('title',{}).get('rendered',''))!=row['title'] or final.get('featured_media')!=media[0]['id'] or media[1]['url'] not in final.get('content',{}).get('rendered',''):raise ValueError('Published translation verification failed')
   receipt={'post_id':post['id'],'url':post['link'],'language':lang,'source_post_id':source_result['post_id'],'status':'published','public_verified':True,'shared_media':media,'new_media_uploads':0,'verified_at':utcnow()};atomic_json(rp,receipt);done[lang]=receipt
   if split and review_state(folder,lang).exists():
    queued=load_json(review_state(folder,lang));queued.update(status='published',next_attempt_at=None,published_receipt=receipt);atomic_json(review_state(folder,lang),queued)
  except Exception as error:
   from .language_review_queue import enabled as independent
   if not independent(DATA) or getattr(error,'code',None) in (401,403,429) or isinstance(getattr(error,'code',None),int) and error.code>=500:raise
   from .failure_diagnostics import failure_details
   from .language_review_queue import publication_failed
   publication_failed(review_state(folder,lang),error)
   done[lang]={'status':'publication_deferred','failure':failure_details(error)}

 atomic_json(status,{'status':'complete' if all(r.get('public_verified') for r in done.values()) else 'pending','languages':done,'at':utcnow()})
 return dict(source_result,translations=done)

def backfill_one(wp,out=OUT):
 cfg=load_json(DATA/'config.json').get('multilingual',{})
 if not cfg.get('enabled'):return None
 for rp in sorted((out/'new').glob('*/wordpress-receipt.json')):
  receipt=load_json(rp);folder=rp.parent
  if receipt.get('public_verified') is not True or not (folder/'article.json').exists():continue
  status=folder/'translations'/'publication-status.json'
  if status.exists() and load_json(status).get('status')=='complete':continue
  schema,_=wp.call('posts',method='OPTIONS')
  if not {'afp_language','afp_source_post_id'}<=schema.get('schema',{}).get('properties',{}).keys():return None
  if cfg.get('independent_publication'):
   from .language_review_queue import handoff,approved
   from .queue import get_topic
   article=load_json(folder/'article.json');topic=get_topic('new',receipt['topic_id']);handoff(topic,article,folder)
   if not any(approved(folder,article,lang) for lang in LANGUAGES):continue
   wp.preflight();return publish_family(wp,folder,topic,receipt)
  if not all((folder/'translations'/f'{lang}.json').exists() for lang in LANGUAGES):
   from .recovery import circuit_open
   if circuit_open('text'):continue
   if all((folder/'translations'/f'{lang}.receipt.json').exists() for lang in LANGUAGES) and status.exists():continue
   finish(start(load_json(folder/'article.json'),folder,load_json(DATA/'health/latest.json')),folder)
  from .queue import get_topic
  wp.preflight();return publish_family(wp,folder,get_topic('new',receipt['topic_id']),receipt)
 return None
