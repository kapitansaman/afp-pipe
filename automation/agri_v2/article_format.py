"""Deterministic FAQ markup matching the site's existing faq-section details/summary pattern."""
import html
# Compatibility export for historical renderers; provenance stays in private artifacts.
DISCLOSURE=''
def faq_html(faq):
 if not isinstance(faq,list) or len(faq)!=3:raise ValueError('Exactly three reviewed FAQs required')
 out=['<h2>سؤالات متداول</h2><div class="faq-section" style="margin-top:24px;border-top:2px solid #eee;padding-top:20px;">']
 for x in faq:
  q=x.get('question','');a=x.get('answer','')
  if not isinstance(q,str) or not isinstance(a,str) or len(q.strip())<10 or len(a.strip())<30:raise ValueError('Complete FAQ question and answer required')
  out.append('<details style="margin-bottom:10px;border:1px solid #ddd;border-radius:5px;padding:10px;"><summary style="cursor:pointer;font-weight:bold;">'+html.escape(q)+'</summary><p style="margin-top:10px;">'+html.escape(a)+'</p></details>')
 return ''.join(out)+'</div>'
