"""Read-only full-queue route audit; does not call models or authorize publication."""
import json
from .queue import DATA,OUT,items,atomic_json,utcnow
from .research_routes import plan,VERSION
from .source_discovery import entries_for

def inspect(data=DATA):
 topics=items('new',data);missing=[];tracks={};leads=0
 for topic in topics:
  try:r=plan(topic)
  except (ValueError,KeyError):missing.append(topic['id']);continue
  tracks[r['track']]=tracks.get(r['track'],0)+1
  if any(e.get('urls') for e in entries_for(topic,data,'scoped-source-catalog.json')):leads+=1
 return {'status':'all_topics_routed' if not missing else 'route_gaps','route_version':VERSION,'checked_at':utcnow(),'topic_count':len(topics),'intent_count':len({t['intent'] for t in topics}),'crop_count':len({t['crop'] for t in topics}),'mapped_topics':len(topics)-len(missing),'unmapped_topic_ids':missing,'track_counts':tracks,'topics_with_discovery_leads':leads,'sources_scientifically_approved':False,'model_calls':0,'published_posts':0}

def run(data=DATA,out=OUT):
 result=inspect(data);atomic_json(out/'parallel/full-queue-research-v1/runtime-route-audit.json',result);return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
