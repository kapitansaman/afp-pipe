"""Optional neutral navigation, never a scientific/product-efficacy claim or publish gate."""
import html,urllib.parse
from .internal_links import canonical,anchors,norm
from .content_matrix import WATER
VERSION='optional-same-language-home-v1'
HOMES={
 'fa-IR':('https://navar-abyari.ir/','نوار تیپ','برای آشنایی با تجهیزات آبیاری، بخش {link} را ببینید.'),
 'en-US':('https://navar-abyari.ir/en/','drip tape','Learn about irrigation equipment: {link}.'),
 'ru-RU':('https://navar-abyari.ir/ru/','капельная лента','Информация об оборудовании для орошения: {link}.'),
 'ar-IQ':('https://navar-abyari.ir/iq/','شريط الري','للتعرّف على معدات الري، راجع {link}.'),
 'tg-TJ':('https://navar-abyari.ir/tj/','лентаи обёрӣ','Маълумот дар бораи таҷҳизоти обёрӣ: {link}.')}

def irrigation_context(topic,brief):
 matrix=topic.get('commercial_matrix') or {}
 return matrix.get('irrigation_relationship')=='direct' or any(WATER.search(str(f.get('claim',''))) for f in brief.get('approved_facts',[]))

def resolve(context,related,language,current_url,verifier=None):
 result={'policy':VERSION,'language':language,'irrigation_context':context is True,'link':None,'status':'not_needed_related_article' if related else 'not_applicable_no_irrigation_context'}
 if related or context is not True:return result
 if language not in HOMES:result['status']='no_configured_same_language_home';return result
 url,anchor,_=HOMES[language]
 if canonical(url)==canonical(current_url):result['status']='skip_self_link';return result
 if verifier is None:
  from .multilingual import verify_target
  verifier=verify_target
 try:
  if verifier(url,language) is not True:raise ValueError('Homepage verification was not affirmative')
 except (ValueError,OSError):
  # Destination verification failure is NOT an assertion of absent related content.
  result['status']='home_verification_failed_optional_link_omitted';return result
 result.update(status='same_language_home_verified',link={'kind':'homepage_fallback','url':url,'anchor':anchor,'language':language});return result

def add(body,row,language):
 if row is None:return body
 if language not in HOMES or (row.get('url'),row.get('anchor'),row.get('language'))!=(*HOMES[language][:2],language):raise ValueError('Exact configured same-language homepage required')
 if any(_same(u,row['url']) for u,text in anchors(body)):verify(body,row);return body
 link='<a href="'+html.escape(row['url'],quote=True)+'">'+html.escape(row['anchor'])+'</a>'
 block='<!-- afp-home-fallback:v1 --><p>'+HOMES[language][2].format(link=link)+'</p>'
 labels={'fa-IR':'سؤالات متداول','en-US':'Frequently asked questions','ru-RU':'Часто задаваемые вопросы','ar-IQ':'الأسئلة الشائعة','tg-TJ':'Саволҳои маъмул'}
 at=body.find('<h2>'+labels[language]+'</h2>');result=body[:at]+block+body[at:] if at>=0 else body+block
 verify(result,row);return result

def _same(a,b):
 try:return canonical(a)==canonical(b)
 except (ValueError,TypeError):return False

def verify(body,row):
 if row is None:return True
 matches=[text for u,text in anchors(body) if _same(u,row['url'])]
 allowed={norm(row['anchor'])}
 if row.get('language')=='fa-IR':allowed|={norm('نوار تیپ'),norm('نوار آبیاری')}
 if len(matches)!=1 or norm(matches[0]) not in allowed:raise ValueError('Homepage fallback must occur exactly once with a relevant keyword')
 return True
