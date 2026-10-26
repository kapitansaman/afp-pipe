"""Commercial editorial context; never evidence, title replacement or publish permission."""
import re
from functools import lru_cache
from .queue import DATA,load_json
from .research_routes import plan
VERSION='search-to-drip-content-matrix-v1'
DIRECT=set('first_water growth_water irrig_duration irrig_interval preharvest_water rain_adjust soil_sensor water_need supplemental uniformity tape_layout tape_length water_productivity greenhouse_drain fertigation'.split())
DISTANT=set('drying grading storage seed_processing curing forage_quality silage toxicity bloat'.split())
WATER=re.compile(r'آبیاری|رطوبت\s*(?:خاک|بستر)|تنش\s*آبی|کم[\s‌]?آبی|غرقاب|irrigation|soil moisture|water stress',re.I)

def contract(topic,brief=None,data=DATA):
 try:route=plan(topic)
 except (KeyError,ValueError):route=None
 intent=topic.get('intent');direct=route is not None and (intent in DIRECT or any(t in topic['title'] for t in ('تیپ','قطره')))
 relation='unclassified' if route is None else 'direct' if direct else 'distant' if intent in DISTANT else 'conditional'
 facts=[] if brief is None else brief.get('approved_facts',[])
 ids=[f['fact_id'] for f in facts if isinstance(f.get('fact_id'),str) and WATER.search(str(f.get('claim','')))]
 mode='equipment_selection' if direct else 'source_supported_bridge' if relation=='conditional' and ids else 'none'
 return {'version':VERSION,'topic_id':topic.get('id'),'canonical_title':topic.get('title'),'crop':topic.get('crop'),'intent':intent,
  'reader_question':topic.get('title'),'reader_task':route['suggested_sections'] if route else [],'business_goal':'Answer the searcher first, then guide a relevant irrigation decision toward actual site drip-tape pages; this is not an encyclopedia or a product advertisement substituted for an answer.',
  'irrigation_relationship':relation,'bridge_fact_ids':ids if relation!='distant' else [],'cta_mode':mode,
  'bridge_requirement':'Integrate only approved irrigation-related facts naturally into the practical answer. No invented causal link from irrigation to yield, quality, disease or profitability. If the exact title is distant or the required evidence is absent, do not force a product bridge.',
  'product_scope':'Existing reviewed drip-tape landing/category pages only. No invented model, price, availability, discount, specification or guaranteed water saving/yield improvement.',
  'cta_rule':'Invitation to inspect suitable options, not an endorsement or field prescription. The site renderer adds verified internal links separately; model must not invent product links.',
  'search_demand_status':demand_status(topic,data),'content_gap_status':'requires_actual_existing_content_audit',
  'queue_action':'retain_canonical_title','publication_authorized':False}

def attach(article,topic,brief):
 return dict(article,commercial_matrix=contract(topic,brief))

def validate(article,topic,brief):
 if 'commercial_matrix' in article and article['commercial_matrix']!=contract(topic,brief):raise ValueError('Commercial matrix/topic/evidence changed')
 return True

def links_enabled(matrix):
 if not isinstance(matrix,dict) or matrix.get('version')!=VERSION:raise ValueError('Unknown commercial matrix')
 if matrix.get('cta_mode') not in ('none','equipment_selection','source_supported_bridge'):raise ValueError('Unknown commercial CTA')
 return matrix['cta_mode']!='none'


@lru_cache(maxsize=8)
def _demand_ids(path,mtime,size):
 row=load_json(path)
 if row.get('version')!=1 or row.get('method')!='normalized_exact_full_title_or_leading_title_clause_only' or row.get('content_gap_inferred') is not False:raise ValueError('Unverified search-demand map')
 return frozenset(row['matched_topic_ids'])

def demand_status(topic,data=DATA):
 path=data/'search-demand-map.json'
 if not path.exists():return 'unknown_not_evaluated'
 st=path.stat();ids=_demand_ids(str(path.resolve()),st.st_mtime_ns,st.st_size)
 return 'exact_phrase_observed_in_supplied_export' if topic.get('id') in ids else 'unknown_not_an_exact_match_in_limited_export'


def commercial_review_flags(article):
 return ['reader_question_answered_before_promotion','product_claims_not_invented','irrigation_bridge_supported_or_omitted'] if 'commercial_matrix' in article else []
