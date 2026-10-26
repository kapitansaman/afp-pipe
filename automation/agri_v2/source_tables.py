"""Preserve simple HTML table column labels, rather than presenting unlabelled numbers.
Complex spans are not inferred. Structured text is deterministic source extraction.
"""
from html.parser import HTMLParser
from .research import clean
class Tables(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.depth=0;self.rows=[];self.row=None;self.cell=None;self.results=[];self.complex=False
 def handle_starttag(self,tag,attrs):
  if tag=='table':
   if self.depth==0:self.rows=[];self.complex=False
   self.depth+=1
  if self.depth!=1:return
  if tag=='tr':self.row=[]
  if tag in ('td','th'):
   if any(k in {'colspan','rowspan'} and v!='1' for k,v in attrs):self.complex=True
   self.cell=[]
 def handle_data(self,data):
  if self.depth==1 and self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if self.depth==1:
   if tag in ('td','th') and self.cell is not None:
    if self.row is not None:self.row.append(clean(' '.join(self.cell)))
    self.cell=None
   if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
   if tag=='table' and self.rows and not self.complex:
    headers=self.rows[0]
    if len(headers)>=2:
     for row in self.rows[1:]:
      if len(row)!=len(headers) or not row[0]:continue
      for i,value in enumerate(row[1:],1):
       if value:self.results.append('[table row] '+row[0]+' | '+headers[i]+': '+value)
  if tag=='table':self.depth=max(0,self.depth-1)

def labelled_rows(raw):
 parser=Tables();parser.feed(raw);return '\n'.join(parser.results[:240])
