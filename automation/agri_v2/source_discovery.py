"""Finite catalog leads are a starting point, never proof of exact topic coverage."""
import re,urllib.parse
from functools import lru_cache
from .queue import load_json
from .research_routes import crop_terms,SPECIFIC_TERMS
INTENT_TERMS={
 'yield':['yield','production','harvest'], 'cut_yield':['alfalfa','cutting','forage','yield'],
 'maturity':['maturity','harvest','ripe'], 'harvest_loss':['harvest','loss','shatter'],
 'storage':['storage','postharvest','handling'], 'germination':['germination','seed'],
 'grading':['grading','quality'], 'density':['spacing','population','density'],
 'transplants':['transplant','spacing'], 'variety':['variety','cultivar','selection']}

@lru_cache(maxsize=128)
def _load_immutable_leads(path,mtime_ns,size):
 return load_json(path)

def _catalog(path):
 stamp=path.stat();return _load_immutable_leads(str(path.resolve()),stamp.st_mtime_ns,stamp.st_size)

@lru_cache(maxsize=1024)
def _matched_index(path,mtime_ns,size,crop):
 index=_load_immutable_leads(path,mtime_ns,size);tokens=crop_terms(crop);matched={};indices=index.get('indices',[])
 for hub in indices+index.get('seed_leads',[]):
  for link in hub.get('links',[]):
   text=urllib.parse.unquote(link['url'])+' '+link.get('label','')
   score=sum(bool(re.search(r'(?<![a-z])'+re.escape(term)+r's?(?![a-z])',text,re.I)) for term in tokens)
   if score:matched[link['url']]=(score,hub['url'])
 return sorted(matched,key=lambda u:(-matched[u][0],u))[:4],[r['url'] for r in indices]

def entries_for(topic,data,primary='research-source-catalog.json'):
 catalogs=[]
 for name in dict.fromkeys([primary,'research-source-catalog.json','scoped-source-catalog.json']):
  path=data/name
  if path.exists():catalogs+=_catalog(path).get('entries',[])
 same=[e for e in catalogs if topic['crop'] in e.get('crops',[])]
 exact=[e for e in same if topic['intent'] in e.get('intents',[])]
 # Never widen the product or canonical title. Fallback pages are discovery leads
 # whose actual crop/product/intent relevance must still pass extraction/review.
 selected=exact or same
 extra=list(dict.fromkeys(u for e in same for u in e.get('urls',[]) if isinstance(u,str)))
 result=[]
 for e in selected:
  seeds=e.get('urls',[])
  result.append(dict(e,discovery_only=not bool(exact),scope=e.get('scope','')+(' Discovery lead only; exact intent coverage is NOT established.' if not exact else ''),
   discovery_terms=list(dict.fromkeys(e.get('discovery_terms',[])+INTENT_TERMS.get(topic['intent'],[])+SPECIFIC_TERMS.get(topic['intent'],[]))),
   discovery_urls=list(dict.fromkeys(e.get('discovery_urls',[])+[u for u in extra if u not in seeds]))[:2]))
 index=data/'university-source-index.json'
 if index.exists():
  verified=_catalog(index)
  for seed in verified.get('seed_leads',[]):
   if topic['crop'] in seed.get('crops',[]):
    result.append({'crops':[topic['crop']],'intents':[topic['intent']],'urls':[seed['url']],
     'scope':seed['scope'],'discovery_only':True,'discovery_terms':crop_terms(topic['crop'])+INTENT_TERMS.get(topic['intent'],[]),
     'observed_source_index':True,'crop_discovery_terms':crop_terms(topic['crop'])})
  crop_tokens=crop_terms(topic['crop']);stamp=index.stat()
  leads,hubs=_matched_index(str(index.resolve()),stamp.st_mtime_ns,stamp.st_size,topic['crop'])
  if leads or not result:
   result.append({'crops':[topic['crop']],'intents':[topic['intent']],'urls':leads,'discovery_urls':hubs[:2],
    'scope':'Observed university links only; exact species, harvested product, intent and local applicability are NOT approved.',
    'discovery_only':True,'discovery_hub_urls':hubs,'crop_discovery_terms':crop_tokens,
    'discovery_terms':INTENT_TERMS.get(topic['intent'],[])+SPECIFIC_TERMS.get(topic['intent'],[])+crop_tokens,
    'observed_source_index':True})
 return result
