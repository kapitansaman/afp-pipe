"""One real query and at most two guarded source reads; no model or publication."""
import tempfile
from . import source_search
from .queue import atomic_json,utcnow
from .parallel_pool import PoolDeferred
from .source_loading import load_documents
from .research import source_host

def run(env,data,out,search_fn=None,fetcher=None):
 report={'version':1,'backend':'tavily','checked_at':utcnow(),'status':'search_connection_blocked','model_calls':0,'published_posts':0,'scientific_acceptance':False,'max_search_requests':1,'max_source_fetches':2}
 out.mkdir(parents=True,exist_ok=True)
 if not source_search.enabled(data):raise ValueError('Search policy disabled')
 with tempfile.TemporaryDirectory(prefix='afp-search-check-') as td:
  e=dict(env);e['AFP_PARALLEL_POOL_DB']=td+'/search.sqlite'
  source_search.initialize(e['AFP_PARALLEL_POOL_DB'],out)
  try:
   source_search.require(e)
   result=(source_search.search if search_fn is None else search_fn)('site:extension.umn.edu dry bean irrigation water management',e,'connection-check')
   from .scoped_sources import fetch
   urls=[r['url'] for r in source_search.validate_results(result['results'])][:2]
   docs=load_documents(urls,fetch if fetcher is None else fetcher,out,source_host,report_path=out/'parallel/source-search/check-fetches.json')
   report.update(status='search_cache_verified' if result['cached'] else 'search_connection_verified',live_connection_verified=not result['cached'],search_cache_hit=result['cached'],admitted_search_results=len(result['results']),fetched_documents=len(docs),fetched_source_urls=[d['url'] for d in docs],evidence_pipeline_verified=bool(docs))
  except source_search.SearchConnectionRequired:report['reason']='tavily_search_connection_required'
  except source_search.SearchProviderError as exc:report.update(reason=exc.category,http_status=exc.http_status,unknown_outcome=exc.http_status is None or exc.http_status>=500)
  except PoolDeferred:report['reason']='search_admission_deferred'
  finally:report['search_usage']=source_search.persist(e['AFP_PARALLEL_POOL_DB'],out)
 atomic_json(out/'parallel/source-search/connection-check.json',report)
 return report
