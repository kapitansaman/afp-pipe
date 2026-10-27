"""Exact, source-bound editorial text corrections. Not a scientific approval or general transliterator."""
import copy
from .queue import DATA,load_json,atomic_json
from .pipeline import digest,numbers

def apply(raw,article,lang,folder,data=DATA):
 path=data/'editorial-corrections/tajik-mixed-script-v1.json'
 if not path.exists():return raw
 config=load_json(path)
 if config.get('version')!=1:raise ValueError('Unknown editorial translation patch version')
 matches=[p for p in config.get('patches',[]) if p.get('language')==lang and p.get('source_article_sha256')==digest(article) and p.get('raw_translation_sha256')==digest(raw)]
 if not matches:return raw
 if len(matches)!=1:raise ValueError('Ambiguous editorial translation patch')
 patch=matches[0];edited=copy.deepcopy(raw);rows=edited.get('translations')
 if not isinstance(rows,list):raise ValueError('Editorial translation shape invalid')
 for update in patch['updates']:
  found=[r for r in rows if r.get('id')==update['id']]
  if len(found)!=1 or found[0].get('text')!=update['old_text']:raise ValueError('Editorial translation original text changed')
  if numbers(update['old_text'])!=numbers(update['new_text']):raise ValueError('Editorial translation patch changed numbers')
  found[0]['text']=update['new_text']
 atomic_json(folder/'translations'/(lang+'.editorial-correction.json'),{'source_article_sha256':digest(article),'original_raw_sha256':digest(raw),'corrected_raw_sha256':digest(edited),'patch_sha256':digest(patch),'updates':patch['updates'],'reason':patch['reason'],'new_model_calls':0,'human_review_claimed':False,'independent_fidelity_review_required':True})
 return edited
