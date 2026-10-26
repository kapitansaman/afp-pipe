"""Near-live, credential-free stage telemetry. Reporting failures never override production safety."""
import base64,datetime,json,os,urllib.request,urllib.error
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow
from .publication_index import verified_publications
STATUS_PATH=DATA/'status/live.json'
REMOTE_PATHS=('data/agri-v2/status/live.json','docs/agri-v2/PROGRESS.md')
BRANCH='feat/agri-generator-v2-2905-merge593'

def metrics():
 receipts=list((OUT/'new').glob('*/wordpress-receipt.json')) if (OUT/'new').exists() else []
 published=sum(load_json(p).get('public_verified') is True for p in receipts)
 held=set(load_json(DATA/'config.json').get('publication_holds',{}));ready=0
 for p in (DATA/'briefs').glob('*.json'):
  b=load_json(p);r=OUT/'new'/b['topic_id']/'wordpress-receipt.json'
  ap=OUT/'new'/b['topic_id']/'cycle-attempts.json'
  from .production_recovery import eligible
  exhausted=ap.exists() and load_json(ap).get('attempts',0)>=2 and not eligible(r.parent)
  if not exhausted and b.get('topic_id') not in held and b.get('publish_authorized') is True and (not r.exists() or not load_json(r).get('public_verified')):ready+=1
 incomplete=sum(load_json(p).get('status')=='incomplete' for p in (OUT/'new').glob('*/state.json'))
 research=[load_json(p) for p in (OUT/'research').glob('*.json')]
 return {'research_briefs_ready':sum(r.get('status')=='brief_ready' for r in research),'research_needs_review':sum(r.get('status')=='needs_review' for r in research),'research_transient_failures':sum(r.get('status')=='transient_failure' for r in research),'new_topics':2905,'original_new_topics':948,'review_origin_topics':1957,'merge_topics':593,'hold_topics':370,'published_verified':published,'remaining_topics':max(0,2905-published),'authorized_unpublished_briefs':ready,'incomplete_topics':incomplete,'publication_held_topics':len(held),'verified_revisions':sum(load_json(p).get('verified') is True for p in (OUT/'new').glob('*/revisions/*/receipt.json'))}

def provider_snapshot():
 p=OUT/'provider-circuit.json';c=load_json(p) if p.exists() else {}
 r=OUT/'pilot-resume/queue-aware-pilot-resume-v1/receipt.json';recovery=load_json(r) if r.exists() else {}
 continuation=OUT/'curated-continuations/pinto-practical85-remaining-images-v1/receipt.json'
 if continuation.exists():
  row=load_json(continuation)
  if row.get('status')!='publication_verified':recovery={'cycles_started':row.get('recovery_resumes',0)}
 deadline=c.get('retry_at_epoch')
 if deadline is None and c.get('open') and c.get('at'):deadline=datetime.datetime.fromisoformat(c['at']).timestamp()+3600
 return {'open':c.get('open') is True and isinstance(deadline,(int,float)) and deadline>datetime.datetime.now(datetime.timezone.utc).timestamp(),'reason':c.get('reason','provider_transient_failure'),'retry_at':datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat() if isinstance(deadline,(int,float)) else None,'recovery_cycles_used':recovery.get('cycles_started',0),'recovery_cycles_limit':2}

def markdown(obj):
 m=obj['metrics'];run=obj.get('run_url','');runline='[مشاهده اجرای جاری]('+run+')' if run else 'اجرای محلی/اولیه'
 last=obj.get('last_task') or {};lastline=('آخرین کار: '+str(last.get('stage',''))+' — '+str(last.get('percent',0))+'٪') if last else ''
 return '\n'.join(['# وضعیت زنده جنراتور کشاورزی AFP','','[داشبورد با به‌روزرسانی خودکار](https://kapitansaman.github.io/afp-pipe/)','',f"**وضعیت:** {obj['status']} — **پیشرفت مرحله‌ای:** {obj['percent']}٪",f"**مرحله:** {obj['stage']}",f"**موضوع:** {obj.get('topic_title') or obj.get('topic_id') or '—'}",f"**آخرین ثبت UTC:** {obj['updated_at']}",runline,lastline,('آخرین نوشته منتشرشده: ['+obj['latest_publication']['title']+']('+obj['latest_publication']['url']+')' if obj.get('latest_publication') else 'هنوز نوشته منتشرشده و تأییدشده‌ای توسط این جنراتور ثبت نشده است.'),'','| شاخص | مقدار |','|---|---:|',f"| موضوع مقاله جدید | {m['new_topics']} |",f"| انتشار تأییدشده توسط این جنراتور | {m['published_verified']} |",f"| موضوع باقی‌مانده | {m['remaining_topics']} |",f"| شرح آماده و دارای مجوز، هنوز منتشرنشده | {m['authorized_unpublished_briefs']} |",f"| شرح‌های ساخته‌شده توسط پژوهشگر | {m.get('research_briefs_ready',0)} |",f"| موضوع پژوهش نیازمند بررسی | {m.get('research_needs_review',0)} |",f"| پژوهش با خطای موقت | {m.get('research_transient_failures',0)} |",f"| موضوع با خروجی ناقص | {m['incomplete_topics']} |",f"| موضوع با انتشار متوقف‌شده | {m.get('publication_held_topics',0)} |",f"| اصلاح تأییدشده | {m['verified_revisions']} |",f"| صف ادغام؛ غیرفعال | {m['merge_topics']} |",f"| بلاتکلیف؛ غیرفعال | {m['hold_topics']} |",'', 'زمان‌بندی: هر ۵ دقیقه، حداکثر یک پست آماده. GitHub ممکن است اجرای زمان‌بندی را با تأخیر شروع کند.','درصد مربوط به مراحل واقعی کار جاری است، نه درصد گذشت زمان یا میزان تکمیل کل ماتریس.','این صفحه داخل مخزن برای دیدن تغییر جدید به بازخوانی نیاز دارد؛ داشبورد وب هر ۱۵ ثانیه داده را می‌خواند.',''])

def publish_file(path,text):
 token=os.environ.get('GITHUB_TOKEN','')
 if not token or os.environ.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe':return False
 base='https://api.github.com/repos/kapitansaman/afp-pipe/contents/'+path
 headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'AFP-stage-status'}
 sha=None
 try:
  with urllib.request.urlopen(urllib.request.Request(base+'?ref='+BRANCH,headers=headers),timeout=12) as r:sha=json.load(r)['sha']
 except urllib.error.HTTPError as e:
  if e.code!=404:return False
 except Exception:return False
 body={'message':'Update AFP live stage [skip ci]','branch':BRANCH,'content':base64.b64encode(text.encode()).decode()}
 if sha:body['sha']=sha
 try:
  with urllib.request.urlopen(urllib.request.Request(base,data=json.dumps(body).encode(),headers=headers,method='PUT'),timeout=12) as r:r.read(1024)
  return True
 except Exception:return False

def update(stage,percent,topic_id=None,topic_title=None,status='running'):
 if os.environ.get('AFP_PROGRESS_ENABLED')!='1':return
 try:
  old=load_json(STATUS_PATH) if STATUS_PATH.exists() else {}
  obj={'version':1,'status':status,'stage':stage,'percent':max(0,min(100,int(percent))),'topic_id':old.get('topic_id') if topic_id is None else topic_id,'topic_title':(old.get('topic_title') if topic_id is None or topic_id==old.get('topic_id') else None) if topic_title is None else topic_title,'updated_at':utcnow(),'run_id':os.environ.get('GITHUB_RUN_ID'),'run_url':('https://github.com/kapitansaman/afp-pipe/actions/runs/'+os.environ['GITHUB_RUN_ID']) if os.environ.get('GITHUB_RUN_ID') else None,'schedule_cron':'*/5 * * * *','max_posts_per_run':1,'metrics':metrics(),'provider':provider_snapshot()}
  publications=verified_publications(OUT)
  obj['latest_publication']=publications[0] if publications else None
  obj['recent_publications']=publications
  obj['last_task']=old.get('last_task') or ({k:old.get(k) for k in ['status','stage','percent','topic_id','topic_title','updated_at','run_url']} if old.get('status') not in (None,'idle') else None)
  if status!='idle':obj['last_task']={k:obj.get(k) for k in ['status','stage','percent','topic_id','topic_title','updated_at','run_url']}
  atomic_json(STATUS_PATH,obj);md=markdown(obj);p=ROOT/REMOTE_PATHS[1];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(md)
  # JSON first so the polling dashboard can advance without waiting for markdown.
  publish_file(REMOTE_PATHS[0],json.dumps(obj,ensure_ascii=False,indent=2)+'\n');publish_file(REMOTE_PATHS[1],md)
 except Exception:print('Progress telemetry temporarily unavailable; no credentials or raw response logged.',flush=True)

def failed(stage='متوقف؛ گزارش اجرای GitHub را بررسی کنید'):
 old=load_json(STATUS_PATH) if STATUS_PATH.exists() else {};update(stage,old.get('percent',0),status='blocked_or_failed')
