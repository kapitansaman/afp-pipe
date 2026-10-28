"""Writer-facing numeric authority matches the unchanged final lexical gate.
Metadata and mathematically correct conversions never promote themselves to facts.
"""
from html.parser import HTMLParser
from .pipeline import numbers,digest
VERSION='approved-fact-numeric-contract-v1'

def allowed(brief):
 return numbers(' '.join(str(f.get('claim',''))+' '+str(f.get('conditions','')) for f in brief.get('approved_facts',[])))

def contract(brief):
 tokens=allowed(brief)
 incidental=numbers(str(brief.get('source_scope_limitations','')))-tokens
 return {'version':VERSION,'authority':'approved_fact_claims_and_conditions_only','allowed_numeric_tokens_exactly':sorted(tokens),'incidental_scope_numeric_tokens_not_authorized':sorted(incidental),'no_digits_authorized':not tokens,'requirements':'This numeric contract is mandatory for ALL generated content_html visible text, table cells, excerpt and FAQ questions/answers. Use only the exact allowed numeric tokens, and only in the meaning, unit, geography, product and conditions of their approved facts. An empty allowlist means NO digit-bearing quantities, dates, years, percentages or numbered labels. Preserve literal source quantities already expressed as words in approved facts; do NOT invent quantities or spell an unapproved number as words to evade validation. Source publication years, source_scope_limitations, outline, title, URL digits and general knowledge are NOT numeric authority. Do not calculate, convert units, round, reformat or add metric equivalents unless the exact resulting tokens AND their conversion have already been approved in the facts. A correct mathematical conversion is still unauthorized if absent from approved claims/conditions. Retain geographic/scope limits in words without copying incidental years. Never change approved facts or suppress a limitation to invent a local recommendation. Passing this lexical contract does not establish scientific or semantic approval.'}

class Visible(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
 def handle_data(self,value):self.parts.append(value)

def audit(raw,brief):
 # unwrap is intentionally identical to the active writer; conflicting objects fail closed.
 from .practical_drafting import unwrap
 _,row=unwrap(raw);parser=Visible();body=row.get('content_html',row.get('html'))
 if isinstance(body,str):parser.feed(body);parser.close()
 texts={'content_html':' '.join(parser.parts),'excerpt':row.get('excerpt') if isinstance(row.get('excerpt'),str) else ''}
 faq=row.get('faq',row.get('faqs'))
 if isinstance(faq,list):
  for i,item in enumerate(faq):
   if isinstance(item,dict):
    for field in ('question','answer'):
     if isinstance(item.get(field),str):texts['faq.'+str(i)+'.'+field]=item[field]
 permitted=allowed(brief);violations=[]
 for field,text in texts.items():
  bad=numbers(text)-permitted
  if bad:violations.append({'field':field,'unapproved_numeric_tokens':sorted(x for x in bad if len(x)<=32),'unapproved_token_count':len(bad)})
 return {'version':VERSION,'raw_sha256':digest(raw),'allowed_numeric_tokens_exactly':sorted(permitted),'violations':violations,'lexical_numeric_contract_passed':not violations,'scientific_approval':False,'candidate_rewritten':False,'final_validation_unchanged':True}
