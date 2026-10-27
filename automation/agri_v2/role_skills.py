"""Small explicit role packs; no training, agent framework or extra model call."""
import hashlib,json
from .queue import DATA
ROLES={'researcher','persian-writer','evidence-reviewer','translator','translation-reviewer','image-reviewer'}
def pack(role,language=None,data=DATA):
 if role not in ROLES:raise ValueError('Unknown role skill')
 p=data/'role-skills'/(role+'.md')
 # Older temporary data fixtures do not silently borrow another workspace's skills.
 if not p.exists():return None
 text=p.read_text(encoding='utf-8');resources=[role+'.md']
 if language=='tg-TJ':
  extra=data/'role-skills/tajik-agriculture.md'
  if not extra.exists():raise ValueError('Tajik role reference missing')
  text+='\n\n'+extra.read_text(encoding='utf-8');resources.append(extra.name)
 if not text.strip() or len(text)>7000:raise ValueError('Role pack must stay concise')
 return {'id':role,'version':1,'language':language,'sha256':hashlib.sha256(text.encode()).hexdigest(),'resources':resources,'instructions':text}
def enrich(prompt,role,language=None,data=DATA):
 skill=pack(role,language,data)
 if not skill:return prompt if isinstance(prompt,str) else json.dumps(prompt,ensure_ascii=False)
 if isinstance(prompt,str):
  try:row=json.loads(prompt)
  except ValueError:row={'task':prompt}
 else:row=dict(prompt)
 if not isinstance(row,dict):raise ValueError('Role task must be an object')
 if 'role_skill' in row:
  if row['role_skill']!=skill:raise ValueError('Conflicting role skill binding')
 else:row['role_skill']=skill
 return json.dumps(row,ensure_ascii=False)
class RoleClient:
 def __init__(self,client,role,language=None,data=DATA):self.base=client;self.role=role;self.language=language;self.data=data
 @property
 def __dict__(self):return self.base.__dict__
 def __getattr__(self,name):return getattr(self.base,name)
 def text(self,prompt,*args,**kwargs):return self.base.text(enrich(prompt,self.role,self.language,self.data),*args,**kwargs)
def for_stage(client,stage,data=DATA):
 role='persian-writer' if stage=='text' else 'evidence-reviewer' if stage in ('article_evidence_review','research_review','existing_content_audit_finalize') or stage.startswith('existing_content_audit') else 'researcher' if stage.startswith('research_') else None
 return RoleClient(client,role,data=data) if role else client
