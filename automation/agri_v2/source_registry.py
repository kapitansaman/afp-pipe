"""Explicit source admission, not truth approval. No arbitrary .org/.com wildcard."""
VERSION='international-institutional-sources-v1'
ACADEMIC_SUFFIXES=('.edu','.ac.uk','.edu.au','.ac.nz','.ac.in','.edu.cn','.ac.jp','.ac.za')
EXACT_HOSTS={
 'extension.org','www.extension.org','fao.org','www.fao.org','openknowledge.fao.org',
 'irri.org','www.irri.org','knowledgebank.irri.org','icrisat.org','www.icrisat.org',
 'cimmyt.org','www.cimmyt.org','nature.com','www.nature.com','academic.oup.com',
 'journals.plos.org','link.springer.com','sciencedirect.com','www.sciencedirect.com',
 'frontiersin.org','www.frontiersin.org'}
def university(host):return any(host.endswith(s) and len(host)>len(s) for s in ACADEMIC_SUFFIXES)
def admitted(host):return university(host) or host.endswith('.gov') or host in EXACT_HOSTS
def institution(host):
 for suffix in sorted(ACADEMIC_SUFFIXES,key=len,reverse=True):
  if host.endswith(suffix):return '.'.join(host.split('.')[-len(suffix.split('.')):])
 return '.'.join(host.split('.')[-2:])
