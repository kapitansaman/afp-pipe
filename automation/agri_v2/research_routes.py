"""Complete, explicit research contracts for the immutable 2905-title queue.
Routing is not evidence sufficiency, human review, or permission to publish.
"""
import json
from pathlib import Path
VERSION='full-queue-research-routes-v1'
GROUPS={
 'scoped_observations':('yield cut_yield stand_age sugar_quality stigma','Original crop/product/region/site/year, harvested basis, denominator and uncertainty; no forecast for Iran.',['تعریف محصول و دامنه','مشاهدات مستند','عوامل مستند تغییر','کاربرد و محدودیت نتایج']),
 'measurement_and_calculation':('density transplants seed_rate planting_material sampling_yield breakeven cost tape_length water_productivity','A source-supported method or dimensionally correct formula, explicitly named measured inputs and units. No fabricated inputs, current prices, example yields or site dimensions.',['داده‌های لازم','روش محاسبه و واحدها','ثبت و کنترل ورودی‌ها','تفسیر و محدودیت کاربرد']),
 'planting_and_establishment':('calendar depth germination seed_quality variety nursery transplant_shock clove corm_health','Exact species/market class, propagule and establishment system. Source-region depths/temperatures/dates are not a local calendar or cultivar recommendation.',['شرایط و تعریف کشت','شواهد استقرار','پایش و تصمیم‌گیری','خطاها و محدودیت انتقال']),
 'irrigation_engineering':('first_water growth_water irrig_duration irrig_interval preharvest_water rain_adjust soil_sensor water_need supplemental uniformity tape_layout greenhouse_drain','Crop stage, measured soil/water/flow inputs and relevant units; distinguish discharge from pressure and crop water use from applied water. Never infer missing flow, tape length or local irrigation duration.',['ورودی‌های اندازه‌گیری‌شده','منطق تصمیم و واحدها','پایش مزرعه یا شبکه','خطاها و حدود کاربرد']),
 'soil_nutrition':('bed compaction fert_plan fertigation organic soil_test salinity','Soil/water/tissue test context, crop and production system. Do not invent fertilizer/pesticide doses or a local prescription; chemical compatibility requires actual evidence.',['آزمایش و وضعیت اولیه','تفسیر شواهد','انتخاب اقدام مشروط','پایش و خطاهای رایج']),
 'diagnosis_and_monitoring':('poor_growth rootrot scouting waterlogging wilt yellow fruit_set blossomrot crack greening hollow bolting forking','Differentiate plausible causes using observed signs and diagnostic/lab evidence; no diagnosis from title alone, no unsourced pesticide rate or toxicity/safety threshold.',['ثبت نشانه‌ها','تشخیص افتراقی مستند','بررسی و اقدام مشروط','زمان نیاز به آزمایش یا متخصص']),
 'harvest_and_postharvest':('maturity harvest_loss drying grading storage seed_processing curing','Exact harvested part, maturity and fresh/dry basis; food/seed/forage conditions must not be interchanged. Every temperature, humidity, loss or storage duration needs literal source support.',['تعریف محصول و هدف','معیارها و شواهد','روش ثبت و کنترل کیفیت','محدودیت‌ها و پیشگیری از خطا']),
 'forage_and_feed_safety':('forage_quality silage toxicity bloat','Species, harvested part and wet/dry basis; toxin/nitrate/cyanogenic/bloat claims require authoritative species-specific evidence. No assertion that forage is safe, no invented feed rate or lab threshold.',['گونه و نوع خوراک','خطر یا کیفیت مستند','نمونه‌برداری و بررسی تخصصی','محدودیت تصمیم و پایش']),
 'crop_management':('regrowth frost heat rotation weeds wintering greenhouse_climate mulch','Crop stage, production system and actual local measurements; only source-supported management criteria, never unsupported causal chains or transferred numeric prescriptions.',['وضعیت و مرحله رشد','معیارهای مستند مدیریت','پایش و اقدامات مشروط','محدودیت‌ها و خطاهای رایج'])}
ROUTES={}
for track,(intents,requirement,sections) in GROUPS.items():
 for intent in intents.split():
  if intent in ROUTES:raise RuntimeError('Duplicate research route')
  ROUTES[intent]={'track':track,'required_evidence':requirement,'suggested_sections':sections}
EXTRA_CROPS={
 'آفتابگردان روغنی':'oilseed sunflower','ارزن':'millet','بادام‌زمینی':'peanut','بادمجان':'eggplant','ترب سیاه':'black radish','توت‌فرنگی':'strawberry','جعفری':'parsley','جو':'barley','جو دوسر':'oat',
 'ذرت دانه‌ای':'grain corn maize','ذرت شیرین':'sweet corn','ذرت علوفه‌ای':'silage forage corn','زیره سبز':'cumin','سورگوم علوفه‌ای':'forage sorghum','سیاه‌دانه':'black cumin Nigella sativa',
 'شلغم':'turnip','شنبلیله':'fenugreek','شوید':'dill','شیرین‌بیان':'licorice','فلفل دلمه‌ای':'bell pepper',
 'لوبیا سبز':'snap green bean','لوبیا سفید':'white dry bean navy Great Northern market classes','لوبیا قرمز':'red kidney dry bean','لوبیا چشم‌بلبلی':'cowpea','لوبیا چیتی':'pinto dry bean','مارچوبه':'asparagus','ماشک':'vetch','نخودفرنگی':'green garden pea','هندوانه تخمی':'watermelon grown for edible seeds','هویج':'carrot','پنبه':'cotton','پیازچه':'scallion green onion','چغندر قند':'sugar beet','چغندر لبویی':'table beet beetroot','کاملینا':'camelina','کدو آجیلی':'pumpkin grown for edible seeds','کدو حلوایی':'winter squash pumpkin fruit','کدو سبز':'summer squash zucchini','کرفس':'celery','کلم بروکلی':'broccoli','کینوا':'quinoa','گلرنگ':'safflower'}
BASE_CROPS=json.loads((Path(__file__).with_name('assets')/'crop-visuals.json').read_text())['CROPS']
CROPS={**BASE_CROPS,**EXTRA_CROPS}
SPECIFIC_TERMS={
 'calendar':['planting','soil temperature','sowing'], 'depth':['planting depth','sowing depth'],
 'seed_rate':['seeding rate','germination','plant population'], 'irrig_duration':['irrigation scheduling','flow rate','application rate'],
 'irrig_interval':['irrigation scheduling','soil moisture'], 'breakeven':['enterprise budget','break even'], 'cost':['enterprise budget','production costs'],
 'toxicity':['nitrate','prussic acid','forage testing'], 'bloat':['bloat','forage safety'], 'stigma':['saffron','stigma','drying'], 'corm_health':['saffron','corm health']}

def plan(topic):
 from .regional_sources import profile,route_queries
 language=topic.get('research_language','fa-IR')
 intent=topic['intent'];crop=topic['crop']
 if intent not in ROUTES:raise ValueError('Unknown explicit research intent: '+str(intent))
 if crop not in CROPS:raise ValueError('Unknown exact crop mapping: '+str(crop))
 route=ROUTES[intent];label=CROPS[crop]
 return {'version':VERSION,'topic_id':topic['id'],'canonical_title':topic['title'],'intent':intent,'crop':crop,'crop_search_label':label,**route,
  'crop_identity_policy':'The English label is a search lead, not cultivar/species equivalence. Preserve the exact named crop, product, market class and growing system. Vetch is not mung bean; cowpea is not common bean; green pea is not dry pea; grain/silage/sweet corn and sugar/table beet differ.',
  'product_ambiguity_policy':'For seed pumpkin and seed watermelon explicitly distinguish whole fruit before extraction from cleaned/dried seed. If the exact title and fetched evidence cannot resolve the product, flag unresolved_scope; never silently replace the title.',
  'source_policy':'One actually fetched directly relevant admitted university source may suffice; otherwise independent institutional sources remain required. Source count alone never proves the title is answerable.',
  'numeric_policy':'Only literal source observations with original units/product/geography and separately verified deterministic conversions; no invented input, unit conversion, price, local rate or forecast.',
  'search_queries':(route_queries(topic,language) if topic.get('regional_research_enabled') else [f'{label} {" ".join(SPECIFIC_TERMS.get(intent,[intent.replace("_"," " )]))} university extension',f'{label} {topic.get("cluster","")} production guide']),
  'publication_authorized':False,'human_review_claimed':False,**({'regional_profile':profile(language)} if topic.get('regional_research_enabled') else {})}

def crop_terms(crop):
 label=CROPS[crop].lower();terms=[label]
 # Search aliases are discovery hints only; article identity remains exact.
 extra={'لوبیا قرمز':['dry bean','dry edible bean','kidney bean'],'لوبیا سفید':['dry bean','dry edible bean','navy bean','great northern'],'لوبیا چیتی':['dry bean','dry edible bean','pinto bean'],'لوبیا سبز':['snap bean','green bean','bean'],
 'ذرت دانه‌ای':['corn','maize'],'ذرت شیرین':['sweet corn'],'ذرت علوفه‌ای':['silage corn','corn silage'],
 'کدو آجیلی':['pumpkin','squash'],'کدو حلوایی':['pumpkin','winter squash'],'کدو سبز':['summer squash','zucchini'],
 'هندوانه تخمی':['watermelon'],'آفتابگردان روغنی':['sunflower'],'فلفل دلمه‌ای':['bell pepper','pepper'],'سورگوم علوفه‌ای':['sorghum'],
 'لوبیا چشم‌بلبلی':['cowpea','southern pea'],'چغندر قند':['sugarbeet','sugar beet'],'چغندر لبویی':['beetroot','table beet','beet'],'سیاه‌دانه':['nigella','black cumin'],'زعفران':['saffron'],'سیب‌زمینی':['potato','potatoes'],'توت‌فرنگی':['strawberry','strawberries'],'ترب سیاه':['radish'],'پیازچه':['scallion','green onion'],'کلزا':['canola','rapeseed'],'موسیر':['shallot'],'پاپریکا':['pepper'],'جو دوسر':['oat'],'گندم':['wheat'],'جو':['barley'],'چاودار':['rye'],'تریتیکاله':['triticale']}
 return list(dict.fromkeys(terms+extra.get(crop,[])))
