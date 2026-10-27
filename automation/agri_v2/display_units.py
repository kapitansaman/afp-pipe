"""Deterministic display-only conversions; original source/evidence never changes.
Ambiguous gallon/thermal accumulation and already dual-unit text need review, not
an invented physical assumption. Conversion output is not sent back to the LLM.
"""
import re,html
from decimal import Decimal,ROUND_HALF_UP
from html.parser import HTMLParser
VERSION='localized-display-units-v1'
LANGS=('fa-IR','en-US','tg-TJ','ar-IQ','ru-RU')
class UnitReviewRequired(ValueError):pass
D=Decimal
DIGITS=str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫−','01234567890123456789.-')
NUM=r'[-−]?[0-9۰-۹٠-٩]+(?:[.٫][0-9۰-۹٠-٩]+)?'
RANGE=r'(?P<a>'+NUM+r')(?:\s*(?P<sep>–|—|-|to|تا|إلى|до)\s*(?P<b>'+NUM+r'))?'
# Longest unit first. Factors map the physical quantity to the metric counterpart.
SPECS=[
 ('m²',r'(?:m²|m2|متر\s*مربع)',D(1),'ft²',D('10.76391041670972')),
 ('m²',r'(?:ft²|sq\.?\s*ft|square\s*feet|فوت\s*مربع)',D('0.09290304'),'ft²',D('10.76391041670972')),
 ('L',r'(?:m³|m3|متر\s*مکعب)',D(1000),'US gal',D('0.2641720523581484')),
 ('kPa',r'(?:bar\b)',D(100),'psi',D('0.1450377377302092')),
 ('kg/ha',r'(?:kg\s*/\s*ha|کیلوگرم\s*(?:در|بر)\s*هکتار)',D(1),'lb/acre',D('0.892179121619')),
 ('kg/ha',r'(?:lb[s]?\s*/\s*acre|پوند\s*(?:در|بر)\s*ایکر)',D('1.120851156194455'),'lb/acre',D('0.892179121619')),
 ('L/min',r'(?:US\s*gal\s*/\s*min)',D('3.785411784'),'US gal/min',D('0.2641720523581484')),
 ('L/min',r'(?:L\s*/\s*min|لیتر\s*(?:در|بر)\s*دقیقه)',D(1),'US gal/min',D('0.2641720523581484')),
 ('ha',r'(?:hectares?|ha|هکتار)',D(1),'acre',D('2.471053814671653')),
 ('ha',r'(?:acres?|ایکر)',D('0.40468564224'),'acre',D('2.471053814671653')),
 ('cm',r'(?:inches|inch|in\.(?=\s|$)|اینچ)',D('2.54'),'in',D('0.3937007874015748')),
 ('cm',r'(?:centimeters?|centimetres?|cm|سانتی[‌ ]?متر)',D(1),'in',D('0.3937007874015748')),
 ('mm',r'(?:millimeters?|millimetres?|mm|میلی[‌ ]?متر)',D(1),'in',D('0.03937007874015748')),
 ('m',r'(?:feet|foot|ft\b|فوت)',D('0.3048'),'ft',D('3.280839895013123')),
 ('m',r'(?:meters?|metres?|m\b|متر)(?![²³23])',D(1),'ft',D('3.280839895013123')),
 ('kg',r'(?:pounds?|lbs?\b|پوند)',D('0.45359237'),'lb',D('2.204622621848776')),
 ('kg',r'(?:kilograms?|kg|کیلوگرم)',D(1),'lb',D('2.204622621848776')),
 ('L',r'(?:US\s*(?:gallons?|gal\b))',D('3.785411784'),'US gal',D('0.2641720523581484')),
 ('L',r'(?:liters?|litres?|L\b|لیتر)',D(1),'US gal',D('0.2641720523581484')),
 ('kPa',r'(?:psi\b)',D('6.894757293168'),'psi',D('0.1450377377302092')),
 ('kPa',r'(?:kPa\b|کیلوپاسکال)',D(1),'psi',D('0.1450377377302092')),
]
def number(v):return D(v.translate(DIGITS))
def fmt(v):
 v=v.quantize(D('0.001'),rounding=ROUND_HALF_UP)
 return format(v,'f').rstrip('0').rstrip('.') if v else '0'
def text(value,lang):
 if lang not in LANGS:raise UnitReviewRequired('Unsupported unit locale')
 # Never change link destinations or literal URL examples.
 parts=re.split(r'(https?://[^\s<>]+)',str(value));return ''.join(p if re.match(r'https?://',p) else _text(p,lang) for p in parts)
def _text(value,lang):
 if re.search(r'(?:degree[ -]?days?|growing[ -]?degree|درجه[‌ -]?روز|°[CF]\s*(?:day|روز))',value,re.I):raise UnitReviewRequired('Thermal accumulation needs typed conversion')
 if re.search(NUM+r'\s*(?:gallons?\b|gal\b|گالن|دونم|dunams?\b)',value,re.I):raise UnitReviewRequired('Gallon system must be explicit')
 if re.search(NUM+r'\s*(?:/|,)\s*'+NUM+r'\s*(?:°[CF]|inch|in\b|feet|ft\b|m\b|cm\b|mm\b|kg\b|lb\b|L\b|اینچ|فوت|متر)',value,re.I):raise UnitReviewRequired('Fraction or comma measurement requires typed parsing')
 if re.search(r'°[CF]\s*/\s*(?:h|hour|min|day)',value,re.I):raise UnitReviewRequired('Temperature rate requires typed conversion')
 # Protect completed generated quantities from subsequent conversion passes.
 # A compound not in the typed table must never be converted one token at a time.
 masked=value
 for metric,pattern,factor,us,us_factor in SPECS:
  if '/' in metric:masked=re.sub(RANGE+r'\s*(?:'+pattern+r')','',masked,flags=re.I)
 if re.search(NUM+r'\s*(?:kg|lb|lbs|L|m³|m3|m²|m2|m|cm|mm|inches|inch|ft|feet|کیلوگرم|لیتر|متر|اینچ)\s*(?:/|per\s|در\s+هر|بر\s)\s*[A-Za-z؀-ۿ]',masked,re.I):raise UnitReviewRequired('Unsupported compound quantity requires typed conversion')
 saved=[]
 def keep(s):saved.append(s);return '\ue000'+str(len(saved)-1)+'\ue001'
 temp=re.compile(RANGE+r'\s*(?:°\s*(?P<symbol>[CFС])\b|(?:degrees?\s*)?(?P<word>Celsius|Fahrenheit)|درجه\s*(?P<fa>سانتی[‌ ]?گراد|سلسیوس|فارنهایت))',re.I)
 def temperature(m):
  unit=(m['symbol'] or m['word'] or m['fa']).lower();is_f=unit.startswith('f') or 'فارنهایت' in unit
  vals=[number(m['a'])]+([number(m['b'])] if m['b'] else [])
  context=value[max(0,m.start()-55):m.start()]
  delta=bool(re.search(r'(?:difference|increase\s+of|decrease\s+of|Δ|اختلاف(?:\s+دما)?|به[‌ ]?اندازه)\s*[^.؛:]{0,20}$',context,re.I))
  tail=value[m.end():m.end()+25]
  if re.match(r'\s*(?:warmer|cooler|above ambient)',tail,re.I):delta=True
  if not delta and re.search(r'(?:increase|decrease|rise|fall|افزایش|کاهش)',context,re.I) and not re.search(r'(?:to|به)\s*$',context,re.I):raise UnitReviewRequired('Ambiguous absolute versus difference temperature')
  want_f=lang=='en-US'
  if is_f!=want_f:
   vals=[v*D(9)/D(5)+(0 if delta else 32) if want_f else (v-(0 if delta else 32))*D(5)/D(9) for v in vals]
  return keep(('–'.join(fmt(v) for v in vals))+' '+('°F' if want_f else '°C'))
 value=temp.sub(temperature,value)
 def dual(m):
  left,right=saved[int(m[1])],saved[int(m[2])]
  if left.endswith(('°C','°F')) and right.endswith(('°C','°F')):
   if left!=right:raise UnitReviewRequired('Conflicting dual temperature needs review')
   return '\ue000'+m[1]+'\ue001'
  return m[0]
 value=re.sub(r'\ue000([0-9]+)\ue001\s*\(\s*\ue000([0-9]+)\ue001\s*\)',dual,value)
 for metric,pattern,factor,us,us_factor in SPECS:
  rx=re.compile(RANGE+r'\s*(?:'+pattern+r')(?![A-Za-z\u0600-\u06ff])',re.I)
  def convert(m,metric=metric,factor=factor,us=us,us_factor=us_factor):
   vals=[number(m['a'])*factor]+([number(m['b'])*factor] if m['b'] else [])
   met='–'.join(fmt(v) for v in vals)+' '+metric
   if lang=='en-US':return keep('–'.join(fmt(v*us_factor) for v in vals)+' '+us+' ('+met+')')
   return keep(met)
  value=rx.sub(convert,value)
 return re.sub('\ue000([0-9]+)\ue001',lambda m:saved[int(m[1])],value)
class Render(HTMLParser):
 def __init__(self,lang):super().__init__(convert_charrefs=True);self.lang=lang;self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  self.parts.append(self.get_starttag_text())
  if tag in ('script','style','code','pre'):self.skip+=1
 def handle_startendtag(self,tag,attrs):self.parts.append(self.get_starttag_text())
 def handle_endtag(self,tag):
  self.parts.append('</'+tag+'>')
  if tag in ('script','style','code','pre'):self.skip=max(0,self.skip-1)
 def handle_data(self,data):self.parts.append(html.escape(data if self.skip else text(data,self.lang),quote=False))
 def handle_entityref(self,name):self.parts.append('&'+name+';')
 def handle_charref(self,name):self.parts.append('&#'+name+';')
 def handle_comment(self,data):self.parts.append('<!--'+data+'-->')
def content(value,lang):
 p=Render(lang);p.feed(value);p.close();return ''.join(p.parts)
