"""Source URLs are retrieval leads, never a reuse of old text or old approval."""
def ordered(brief,documents):
 from .regional_sources import RegionalBlocked,credible
 from .scoped_research import tokens
 if not isinstance(brief,dict) or not isinstance(brief.get('sources'),list) or not isinstance(brief.get('approved_facts'),list):raise RegionalBlocked('regional_declared_source_binding_invalid')
 sources={s.get('url') for s in brief['sources'] if isinstance(s,dict) and isinstance(s.get('url'),str)}
 facts=brief['approved_facts'];rows=[]
 for fact in facts:
  if not isinstance(fact,dict):raise RegionalBlocked('regional_declared_source_binding_invalid')
  url=fact.get('source_url')
  if url is None:continue # qualitative model knowledge is not an invented URL
  if not isinstance(url,str) or url not in sources:raise RegionalBlocked('regional_declared_source_binding_invalid')
  try:admitted=credible(url)
  except (ValueError,TypeError):admitted=False
  if not admitted:raise RegionalBlocked('regional_declared_source_binding_invalid')
  required=set() if fact.get('kind')=='deterministic_conversion' else tokens(fact.get('claim',''))
  missing=bool(required) and not any(not required-tokens(d['text']) for d in documents)
  rows.append((not missing,url))
 result=[]
 # Stable priority for literal numeric gaps, followed by the remaining original
 # source leads. Numeric presence is NOT scientific support or locality proof.
 for _,url in sorted(rows,key=lambda r:r[0]):
  if url not in result:result.append(url)
 if len(result)>6:raise RegionalBlocked('regional_declared_source_fetch_cap')
 return result
