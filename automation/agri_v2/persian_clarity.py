"""Exact, source-bound editorial revision; no automatic scientific approval."""
import copy
from .queue import load_json
from .pipeline import digest,validate_article,validate_for_publication,numbers
from .multilingual import source_segments
from .text_fields import plain_citations

def apply(article,topic,brief,patch):
 if patch.get('source_article_sha256')!=digest(article):raise ValueError('Persian editorial input changed')
 parser,values=source_segments(article);new=list(values);seen=set()
 for change in patch['changes']:
  i=change['id']
  if type(i)is not int or i in seen or not 0<=i<len(values) or values[i]!=change['old_text']:raise ValueError('Persian editorial selection changed')
  if numbers(plain_citations(values[i])[0])!=numbers(change['new_text']):raise ValueError('Persian editorial numbers changed')
  new[i]=change['new_text'];seen.add(i)
 n=len(parser.texts);result=copy.deepcopy(article);result.update(content_html=parser.render(new),title=new[n],excerpt=new[n+1],faq=[{'question':plain_citations(new[n+2+j*2])[0],'answer':plain_citations(new[n+3+j*2])[0]} for j in range(3)])
 if result['title']!=article['title']:raise ValueError('Canonical title changed')
 validate_article(result,topic,brief);validate_for_publication(result)
 return result,{'source_article_sha256':digest(article),'edited_article_sha256':digest(result),'changed_segment_ids':sorted(seen),'approved_source_urls':[s['url'] for s in brief['sources']],'independent_evidence_review_required':True,'human_review_claimed':False,'old_translations_reused_or_rebound':False}
