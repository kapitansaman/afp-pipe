"""Bounded parallel source I/O; only structurally validated fetched evidence is cached."""
import hashlib,re,urllib.error
from concurrent.futures import ThreadPoolExecutor
from .queue import load_json,atomic_json,age_hours
TTL_HOURS=6
MAX_WORKERS=3

def valid_document(doc,url,source_host):
 try:
  source_host(url);source_host(doc['url'])
  chain=doc.get('redirect_chain',[url])
  if not isinstance(chain,list) or not 1<=len(chain)<=5 or chain[0]!=url or chain[-1]!=doc['url'] or len(set(chain))!=len(chain):return False
  for target in chain:source_host(target)
  return (doc.get('requested_url',doc['url'])==url and isinstance(doc['text'],str) and 500<=len(doc['text'])<=24000
   and doc['sha256']==hashlib.sha256(doc['text'].encode()).hexdigest()
   and 0<=age_hours(doc['fetched_at'])<TTL_HOURS)
 except (KeyError,TypeError,ValueError):return False

def load_documents(urls,fetcher,out,source_host,report_path=None,minimum_link_version=0):
 urls=list(dict.fromkeys(u for u in urls if isinstance(u,str)))[:6]
 reports={}
 def one(url):
  path=out/'source-cache'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
  try:
   source_host(url)
   try:cached=load_json(path)
   except (OSError,ValueError):cached=None
   if isinstance(cached,dict) and valid_document(cached,url,source_host) and cached.get('source_link_discovery_version',0)>=minimum_link_version:
    reports[url]={'url':url,'canonical_url':cached['url'],'status':'cache_valid'};return cached
   doc=fetcher(url)
   if not valid_document(doc,url,source_host):raise ValueError('invalid_fetched_document')
   atomic_json(path,doc)
   reports[url]={'url':url,'canonical_url':doc['url'],'redirect_hops':len(doc.get('redirect_chain',[url]))-1,'status':'fetched'}
   return doc
  except Exception as exc:
   row={'url':url,'status':'unavailable','category':'fetch_or_validation_failed','temporary':True}
   if isinstance(exc,urllib.error.HTTPError):row.update(category='http_error',http_status=exc.code,temporary=exc.code in {401,403,408,425,429} or exc.code>=500)
   elif isinstance(exc,(TimeoutError,urllib.error.URLError)):row['category']='network_or_timeout'
   elif isinstance(exc,ValueError):
    code=str(exc)
    if re.fullmatch(r'scoped_source_http_[1-5][0-9]{2}',code):row.update(category='http_error',http_status=int(code.rsplit('_',1)[1]),temporary=int(code.rsplit('_',1)[1]) in {401,403,408,425,429} or int(code.rsplit('_',1)[1])>=500)
    else:row.update(category='source_policy_or_content_rejected',temporary=False)
   reports[url]=row
   return None
 with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
  found=[d for d in pool.map(one,urls) if d is not None]
 documents=list({d['url']:d for d in reversed(found)}.values())[::-1]
 if report_path is not None:atomic_json(report_path,{'requested':len(urls),'loaded':len(documents),'sources':[reports[u] for u in urls]})
 return documents
