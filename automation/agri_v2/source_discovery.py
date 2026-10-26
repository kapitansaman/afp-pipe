"""Finite catalog leads are a starting point, never proof of exact topic coverage."""
from .queue import load_json
INTENT_TERMS={
 'yield':['yield','production','harvest'], 'cut_yield':['alfalfa','cutting','forage','yield'],
 'maturity':['maturity','harvest','ripe'], 'harvest_loss':['harvest','loss','shatter'],
 'storage':['storage','postharvest','handling'], 'germination':['germination','seed'],
 'grading':['grading','quality'], 'density':['spacing','population','density'],
 'transplants':['transplant','spacing'], 'variety':['variety','cultivar','selection']}

def entries_for(topic,data,primary='research-source-catalog.json'):
 catalogs=[]
 for name in dict.fromkeys([primary,'research-source-catalog.json','scoped-source-catalog.json']):
  path=data/name
  if path.exists():catalogs+=load_json(path).get('entries',[])
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
   discovery_terms=list(dict.fromkeys(e.get('discovery_terms',[])+INTENT_TERMS.get(topic['intent'],[]))),
   discovery_urls=list(dict.fromkeys(e.get('discovery_urls',[])+[u for u in extra if u not in seeds]))[:2]))
 return result
