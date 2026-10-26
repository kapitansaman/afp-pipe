"""One owned pilot; source corrections are versioned, never an approval or budget reset."""
import copy,hashlib,json,re,shutil
from pathlib import Path
from .queue import atomic_json,load_json,utcnow,age_hours
TOPIC='agri-621734b38aa9'
REVISION='white-bean-source-correction-v1'
PDF='https://extensionpubs.unl.edu/publication/ec3064/2023/pdf/view/ec3064-2023.pdf'
IOWA='https://www.extension.iastate.edu/alternativeag/dry-edible-bean'

def select_topics(topics):
 selected=[t for t in topics if t['id']==TOPIC]
 if len(selected)!=1:raise ValueError('pilot_topic_must_retain_existing_family_owner')
 return selected

def table_windows(text):
 # Only literal contiguous text is returned; no invented labelled table rows.
 windows=[]
 for m in re.finditer(r'Table\s+\d+\.\s+\d{4}[^.]{1,150}Ag Lab\.',text):
  tail=text[m.start():];end=re.search(r'\[page\s+\d+\]|Table\s+\d+\.',tail[len(m[0]):])
  quote=tail[:len(m[0])+end.start()] if end else tail
  if 80<=len(quote)<=6000 and re.match(r'\s+Ent\s+PEDIGREE\s+Yield at 14%',quote[len(m[0]):]) and 'lbs/acre' in quote[:350]:windows.append(quote)
 return windows

def table_measurement(binding,quote):
 b=binding.get('table_measurement')
 if not isinstance(b,dict) or set(b)!={'table_title','row_label','unit','moisture_basis'}:raise ValueError('typed_yield_table_binding_required')
 if b['unit']!='lb/acre' or b['moisture_basis']!='14%':raise ValueError('unsupported_table_measurement_basis')
 windows=[q for q in table_windows(quote) if q.startswith(b['table_title'])]
 if len(windows)!=1:raise ValueError('unique_literal_yield_table_required')
 q=windows[0]
 if q!=binding['unit_quote'] or not re.fullmatch(r'\d+ White Pearl',b['row_label']):raise ValueError('literal_table_row_binding_required')
 rows=re.findall(r'(?<!\w)'+re.escape(b['row_label'])+r'\s+(\d+)\s+\d+\s+\d+\s+\d+(?:\.\d+)?\s+',q)
 if rows!=[binding['value']]:raise ValueError('yield_value_must_be_first_measurement_column')
 return True

def build_candidate(topic,old,docs):
 from .research import evidence_catalog
 from .scoped_research import validate_candidate
 catalog=evidence_catalog(docs);facts=[]
 for num,site,value,label in [(1,'Scottsbluff','3633','15 White Pearl'),(2,'Mitchell','5057','15 White Pearl')]:
  title=f'Table {num}. 2022 Great Northern Variety Trial— {site} Ag Lab.'
  matches=[e for e in catalog if e['source_url']==PDF and e['quote'].startswith(title) and e['id'].split('-')[-1].startswith('t')]
  if len(matches)!=1:raise ValueError('expected_observed_table_not_available')
  e=matches[0];q=e['quote'];basis=re.search(r'Yield at 14%[^%]{0,250}lbs/acre',q)
  if not basis:raise ValueError('literal_yield_moisture_header_required')
  bindings=[{'value':value,'unit_quote':q,'geographic_scope':site+', western Nebraska, USA; trial year 2022','product_scope':'Great Northern dry bean, White Pearl; yield adjusted to 14% moisture','table_measurement':{'table_title':title,'row_label':label,'unit':'lb/acre','moisture_basis':'14%'}},{'value':'14','unit_quote':basis[0],'geographic_scope':site+', Nebraska, USA','product_scope':'dry bean yield moisture basis'}]
  facts.append({'kind':'source_observation','claim':f'در آزمایش Great Northern در {site} نبراسکا، عملکرد رقم White Pearl برابر {value} پوند در ایکر با تعدیل به رطوبت ۱۴ درصد گزارش شده است.','conditions':'این عدد مشاهدهٔ همان رقم و محل آزمایش در ایالات متحده است؛ میانگین همه ارقام، پیش‌بینی مزرعه ایران، توصیه انتخاب رقم یا تضمین عملکرد نیست.','evidence_id':e['id'],'numeric_bindings':bindings})
 for needle,claim,conditions in [
  ('Great Northerns, navy beans or mixes of beans','منبع معرفی لوبیای خشک، Great Northern و navy را از انواعی می‌داند که به صورت دانه کامل و فرآوری‌نشده به فروش می‌رسند.','این شاهد صرفاً برای تعریف محصول دانه خشک است، نه اثبات هم‌ارزی با هر رقم محلی لوبیا سفید یا اندازه‌گیری عملکرد ایران.'),
  ('rains at the time of harvest can cause discoloration','در متن مربوط به میسوری، باران هنگام برداشت از عوامل تغییر رنگ دانه، به‌ویژه در نوع سفید navy، معرفی شده است.','این نقل‌قول درباره کیفیت دانه و زمینه اقلیمی میسوری در آمریکاست؛ درصد خسارت یا رابطه عددی برای عملکرد مزرعه ایران از آن نتیجه گرفته نمی‌شود.')]:
  matches=[e for e in catalog if e['source_url']==IOWA and needle in e['quote']]
  if not matches:raise ValueError('independent_literal_context_missing')
  e=min(matches,key=lambda x:len(x['quote']));facts.append({'kind':'qualitative','claim':claim,'conditions':conditions,'evidence_id':e['id'],'numeric_bindings':[]})
 value={k:copy.deepcopy(old[k]) for k in ['topic_id','slug','outline','product_definition']}
 value.update(answers_intent=True,local_prescription=False,facts=facts,review_schema_version=2,evidence_revision=REVISION)
 validate_candidate(topic,value,docs);return value

def prepare(topic,data,out,fetcher=None):
 if topic['id']!=TOPIC:raise ValueError('one_explicit_white_bean_topic_only')
 folder=out/'new'/TOPIC;ev=folder/'lifecycle-evidence';dest=ev/'revisions'/REVISION;receipt=dest/'receipt.json'
 if receipt.exists():
  proof=load_json(receipt)
  for name in ('candidate.json','sources.json'):
   if hashlib.sha256((ev/name).read_bytes()).hexdigest()!=proof['current_sha256'][name]:raise ValueError('pilot_evidence_changed_after_revision')
  if age_hours(load_json(ev/'sources.json')['documents'][0]['fetched_at'])>=6:raise ValueError('pilot_sources_expired_requires_new_review_not_timestamp_refresh')
  return proof
 if dest.exists():raise ValueError('incomplete_revision_requires_reconciliation')
 if (data/'briefs'/(TOPIC+'.json')).exists() or (folder/'article.json').exists():raise ValueError('never_replace_approved_brief_or_article')
 old=load_json(ev/'candidate.json')
 if old['topic_id']!=TOPIC:raise ValueError('candidate_identity_mismatch')
 if fetcher is None:
  from .scoped_sources import fetch as fetcher
 from .source_loading import valid_document
 from .research import source_host
 docs=[fetcher(PDF),fetcher(IOWA)]
 if any(not valid_document(d,u,source_host) for d,u in zip(docs,[PDF,IOWA])):raise ValueError('fresh_literal_sources_required')
 candidate=build_candidate(topic,old,docs)
 # Preserve all previous files and failed reviews. Stage counters are never touched.
 for name in ['candidate.json','sources.json','review-raw.json']:
  if (ev/name).exists():
   target=dest/'previous'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ev/name,target)
 atomic_json(ev/'sources.json',{'documents':docs,'mode':'automated_scoped_evidence_review_v1','source_text_layout_version':2})
 atomic_json(ev/'candidate.json',candidate)
 proof={'revision':REVISION,'topic_id':TOPIC,'created_at':utcnow(),'approved':False,'prior_review_overridden':False,'original_attempts_reset':False,'outline_and_canonical_scope_unchanged':True,'removed':'generic Missouri dry-bean bushel range; unsupported broad geography and yield-causation claims','added':'literal White Pearl Great Northern yield rows; exact source moisture basis; deterministic mass/area conversion','current_sha256':{n:hashlib.sha256((ev/n).read_bytes()).hexdigest() for n in ['candidate.json','sources.json']}}
 atomic_json(receipt,proof);return proof
