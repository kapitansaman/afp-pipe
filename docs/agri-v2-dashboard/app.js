'use strict';
const $=id=>document.getElementById(id);
const fa=new Intl.NumberFormat('fa-IR');
const languages={'ru-RU':'روسی','ar-IQ':'عربی','tg-TJ':'تاجیکی','en-US':'انگلیسی'};
const states={waiting:'در انتظار تلاش بعدی',reserved:'تلاش رزرو شده',approved:'تأییدشده',published:'منتشرشده',needs_attention:'نیازمند بررسی',publication_needs_attention:'اشکال در انتشار',source_changed:'منبع تغییر کرده',failed:'ناموفق',deferred:'موکول‌شده',validated:'مرحله تأییدشده',assigned:'واگذار شده'};
const stages={text:'تولید متن',article_evidence_review:'بازبینی منابع متن',research_sources:'یافتن منبع',research_extract:'استخراج شواهد',research_validate_saved:'اعتبارسنجی شواهد',research_review:'بازبینی پژوهش',existing_content_audit:'بررسی محتوای قبلی',existing_content_audit_required:'نیازمند بررسی هم‌پوشانی',scope_review_required:'بررسی دامنه پژوهش',research_needs_review:'بازبینی پژوهش',research_budget_exhausted:'سقف تلاش پژوهش',ready_for_drafting:'آماده تولید متن',source_discovery_required:'نیازمند منبع','image-1':'تصویر اول','image-2':'تصویر دوم','vision-1':'بازبینی تصویر اول','vision-2':'بازبینی تصویر دوم',publish:'انتشار',translations_pending:'ترجمه‌ها باقی مانده',unknown:'گزارش موجود نیست'};
let loading=false,lastSnapshot=null;
function num(v){return typeof v==='number'&&Number.isFinite(v)?fa.format(v):'—';}
function time(value,short=false){const d=new Date(value||'');if(!Number.isFinite(+d))return 'زمان نامشخص';return d.toLocaleString('fa-IR',{timeZone:'Europe/Istanbul',month:'short',day:'numeric',...(short?{}:{hour:'2-digit',minute:'2-digit'})});}
function node(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function safeURL(value,site='github.com'){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname===site&&!u.username&&!u.password&&(!u.port||u.port==='443')&&(site!=='github.com'||u.pathname.startsWith('/kapitansaman/afp-pipe/'))?u.href:null;}catch{return null;}}
function link(el,url){const valid=safeURL(url);el.href=valid||'https://github.com/kapitansaman/afp-pipe/actions';}
function stageLabel(s){if(stages[s])return stages[s];for(const prefix of ['language_primary-','translation-'])if((s||'').startsWith(prefix))return 'ترجمه و بازبینی '+(languages[s.slice(prefix.length)]||'زبان');if((s||'').startsWith('existing_content_audit-'))return 'بررسی محتوای قبلی';return 'مرحله فنی؛ مشاهده گزارش';}
function render(d){
 if(!d||d.version!==2||!d.metrics||!d.automation)throw Error('invalid snapshot');
 const a=d.automation,m=d.metrics,h=d.health||{},e=d.experiment;
 const off=a.schedule_enabled!==true||a.automatic_generation!==true;
 $('mode').textContent=off?'اجرای خودکار خاموش':'اجرای خودکار پیکربندی شده';
 $('headline').textContent=off?'جنراتور در مرحلهٔ آماده‌سازی است':a.research_only?'تولید اصلی در حالت پژوهش است':'وضعیت انتشار را از گزارش اجرا بررسی کنید';
 $('summary').textContent=a.independent_languages?'بازبینی هر زبان مستقل است؛ مورد مشکل‌دار در صف جدا می‌ماند.':'انتشار فقط پس از عبور از کنترل‌های تولید انجام می‌شود.';
 $('remaining').textContent=num(m.remaining);$('total-note').textContent='از '+num(m.total)+' عنوان';$('published').textContent=num(m.published);$('review-count').textContent=num(m.review_waiting);
 $('review-note').textContent=m.review_approved?'همچنین '+num(m.review_approved)+' زبان تأییدشده':'در صف جداگانه';
 $('keys').textContent=h.bound?num(h.text_ok)+' از '+num(h.capacity):'نامشخص';
 const healthAge=(Date.now()-Date.parse(h.checked_at))/3600000;
 $('health-note').textContent=!h.bound?'گزارش معتبر موجود نیست':healthAge<0||!Number.isFinite(healthAge)?'زمان آزمون نامشخص':healthAge>=24?'آزمون قدیمی؛ نیازمند تجدید':'آزمون '+time(h.checked_at);
 if(e){
  $('experiment-title').textContent=e.title||'آزمون فنی';
  const rows=[['فارسی',e.source_reviewed?'منبع تأیید شد':'بررسی ثبت نشده',e.source_reviewed?'good':'neutral'],['تاجیکی',e.tajik_quality_pending?'نیازمند بررسی':e.native_review_done?'بازبینی مستقل شد':'تأیید مستقل ندارد',e.tajik_quality_pending?'attention':'neutral'],['تصویر',e.image_calls===0?'آزموده نشد':'مشاهده گزارش','neutral'],['انتشار',e.published_posts===0?'منتشر نشد':'مشاهده گزارش','neutral']];
  $('experiment-stages').replaceChildren(...rows.map(([label,value,tone])=>{const x=node('div',null,'stage');x.dataset.tone=tone;x.append(node('span',label),node('strong',value));return x;}));
  $('experiment-meta').textContent=time(e.at)+(typeof e.model_calls==='number'?' · '+num(e.model_calls)+' درخواست متن':'');link($('experiment-link'),e.run_url);
 }else{$('experiment-title').textContent='آزمایشی ثبت نشده';$('experiment-stages').replaceChildren();$('experiment-meta').textContent='—';}
 const blockers=[];
 if(a.research_only)blockers.push(['آزادسازی تولید عمومی','تولید اصلی هنوز پژوهش‌محور است.']);
 if(e?.tajik_quality_pending)blockers.push(['کیفیت تاجیکی','تأیید خودکار مدل، تأیید نهایی زبان نیست.']);
 if(!h.bound||!h.image_ok||healthAge>=24)blockers.push(['شاهد تازهٔ سلامت تصویر','آزمون متن جای آزمون تصویر را نمی‌گیرد.']);
 $('blocker-count').textContent=num(blockers.length);
 $('blockers').replaceChildren(...(blockers.length?blockers:[['مانع ثبت‌شده‌ای در این خلاصه نیست','آمادگی انتشار باید در گزارش اجرای واقعی تأیید شود.']]).map(([title,detail])=>{const li=node('li');if(!blockers.length)li.className='clear';const text=node('div',title);text.append(node('small',detail));li.append(text);return li;}));
 const reviews=(Array.isArray(d.reviews)?d.reviews:[]).filter(r=>r.status!=='published');
 $('queue-count').textContent=num(reviews.length);$('queue-empty').hidden=reviews.length>0;$('queue-table').hidden=!reviews.length;
 $('queue-body').replaceChildren(...reviews.map(r=>{
  const tr=node('tr'),topic=node('td'),state=node('td'),history=node('td'),next=node('td');
  topic.append(node('div',r.title||r.topic_id),node('small',(languages[r.language]||'زبان نامشخص')+(r.experimental_only?' · آزمایشی':'')));
  state.append(node('span',states[r.status]||'مشاهده پرونده','tag '+(r.status==='approved'?'good':r.status==='needs_attention'||r.status==='publication_needs_attention'?'attention':'neutral')));
  history.append(node('span',num(r.attempts)+(r.experimental_only?' دور قبلی':' تلاش')),node('small',num(r.model_calls_spent)+' درخواست'));
  const eligible=r.publication_next_attempt_at||r.next_attempt_at;
  if(eligible&&!r.experimental_only)next.append(node('small','زودتر از '+time(eligible)+' نه؛ با اجرای بعدی'));
  const action=node('a',r.experimental_only?'بررسی کیفیت زبان ↗':r.status==='approved'?'بررسی انتشار ↗':'پرونده اصلاح ↗');action.target='_blank';action.rel='noopener noreferrer';link(action,r.state_url);next.append(action);tr.append(topic,state,history,next);return tr;
 }));
 const p=(d.publications||[]).find(x=>x.public_verified===true&&safeURL(x.url,'navar-abyari.ir')&&typeof x.title==='string'&&x.title.trim());
 $('publication').hidden=!p;if(p){$('publication-link').textContent=p.title+' ↗';$('publication-link').href=safeURL(p.url,'navar-abyari.ir');$('publication-date').textContent=time(p.published_at||p.verified_at,true);}
 const detail=[['مدل متن',h.text_model||'نامشخص'],['مدل تصویر',h.image_model||'نامشخص'],['مدل آخرین آزمایش',e?.model||'نامشخص'],['ظرفیت طراحی',num(a.configured_workers)+' خانواده؛ نه تعداد اجرای فعال'],['صف ادغام / نگه‌داری',num(m.merge)+' ادغام · '+num(m.hold)+' نگه‌داری'],['تست‌های محلی',num(d.local_tests?.passed)+'؛ نه آزمون زنده'],['آخرین آزمون کلید',time(h.checked_at)],['آخرین اجرای تولید اصلی',time(d.last_lifecycle?.at)]];
 $('technical-data').replaceChildren(...detail.map(([label,value])=>{const div=node('div');div.append(node('dt',label),node('dd',value));return div;}));
 $('owners-count').textContent=num((d.families||[]).length)+' موضوع واگذارشده';
 $('families-body').replaceChildren(...(d.families||[]).map(f=>{const tr=node('tr');tr.append(node('td',f.title),node('td',stageLabel(f.stage)),node('td',f.public_verified?'انتشار تأییدشده':states[f.status]||'مشاهده گزارش'));return tr;}));
 $('snapshot-time').textContent='ثبت خلاصه: '+time(d.generated_at)+' · استانبول';
 $('connection').textContent='اطلاعات دریافت شد';
 lastSnapshot=d;
}
async function currentRun(){
 try{
  const r=await fetch('https://api.github.com/repos/kapitansaman/afp-pipe/actions/runs?per_page=30',{cache:'no-store'});if(!r.ok)throw Error('runs unavailable');const d=await r.json();if(!Array.isArray(d.workflow_runs))throw Error('invalid runs');
  const active=d.workflow_runs.find(x=>['in_progress','queued','waiting','requested','pending'].includes(x.status)&&/^AFP (one-shot owner operation|parallel -|adaptive scheduler|agri v2 -)/.test(x.name||'')&&!/dashboard/i.test(x.name||''));
  $('running').textContent=active?(active.status==='in_progress'?'در حال اجرا':'در صف اجرا'):'اجرای فعالی ثبت نشده';link($('run-link'),active?.html_url||lastSnapshot?.experiment?.run_url||lastSnapshot?.last_lifecycle?.run_url);
 }catch{$('running').textContent='اجرای جاری قابل بررسی نیست';}
}
async function refresh(){
 if(loading)return;loading=true;$('refresh').disabled=true;$('connection').textContent='در حال به‌روزرسانی…';
 try{const r=await fetch('status.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('snapshot unavailable');render(await r.json());$('notice').hidden=true;}
 catch{$('connection').textContent='خطای دریافت';$('notice').hidden=false;$('notice').textContent=lastSnapshot?'ارتباط برقرار نشد؛ آخرین اطلاعات حفظ شده است.':'داده وضعیت در دسترس نیست. گزارش GitHub را بررسی کنید.';}
 finally{await currentRun();loading=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);refresh();setInterval(()=>{if(!document.hidden)refresh();},60000);
