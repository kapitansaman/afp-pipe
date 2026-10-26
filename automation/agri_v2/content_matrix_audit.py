"""Read-only commercial matrix export; no queue mutation, paid model or publication."""
import csv,json
from .queue import DATA,OUT,items,atomic_json,utcnow
from .content_matrix import contract,VERSION

def run(data=DATA,out=OUT):
 topics=items('new',data);dest=out/'parallel/commercial-content-matrix-v1';dest.mkdir(parents=True,exist_ok=True);rows=[]
 for t in topics:
  c=contract(t,data=data);rows.append({'topic_id':t['id'],'title':t['title'],'crop':t['crop'],'intent':t['intent'],'irrigation_relationship':c['irrigation_relationship'],'planning_cta_mode':c['cta_mode'],'search_demand_status':c['search_demand_status'],'queue_action':c['queue_action'],'content_gap_status':c['content_gap_status'],'publication_authorized':False})
 with (dest/'topic-content-matrix.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 report={'version':VERSION,'checked_at':utcnow(),'topic_count':len(topics),'mapped_topic_count':sum(r['irrigation_relationship']!='unclassified' for r in rows),'canonical_titles_preserved':all(t['title']==r['title'] for t,r in zip(topics,rows)),'topic_deletions':0,'models_called':0,'published_posts':0,'source_sufficiency_waived':False,'schedule_activated':False,'source_metrics_published':False,'conditional_cta_rule':'Re-evaluate against approved fact IDs at writing time. An unknown search match does not remove or deprioritize a topic.','scope':'This is a new-article editorial matrix, not automatic topic rejection, confirmed content-gap analysis or a rewrite of historical accepted work.'}
 atomic_json(dest/'validation.json',report);return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
