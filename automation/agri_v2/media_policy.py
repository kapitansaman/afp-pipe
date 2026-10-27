"""Versioned topic-aware scenes; locked AFP identity, proportional reference, no output paste-up."""
import base64,io,json,re,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
PHONE_LABEL='AFP | 09134922013'
POLICY='agri-topic-scene-aghala-v6-topic-routed'
ASSETS=Path(__file__).with_name('assets')
CROP_DATA=json.loads((ASSETS/'crop-visuals.json').read_text())
def norm(value):
 return re.sub(r'\s+',' ',str(value).translate(str.maketrans('يك','یک')).replace('‌',' ')).strip()
def reference_product():
 raw=base64.b64decode((ASSETS/'afp-tape.webp.b64').read_text().strip(),validate=True)
 product=Image.open(io.BytesIO(raw)).convert('RGB');product.thumbnail((240,210),Image.Resampling.LANCZOS)
 return product
def use_red_bean_close(topic):
 text=norm((topic or {}).get('crop','')+' '+(topic or {}).get('title',''))
 return 'لوبیا قرمز' in text and any(x in text for x in ('برداشت','رسیدگی','خشک'))
def needs_filter(topic):
 # Hardware is a topic requirement, never an invented requirement for every article.
 text=norm((topic or {}).get('title',''))
 return any(term in text for term in ('فیلتر','فیلتراسیون','filter','filtration'))
def reference_images(kind=None,topic=None):
 if kind==3 and needs_filter(topic):
  encoded=(ASSETS/'closed-y-filter-scene.webp.b64').read_text().strip()
 else:
  # Original product bytes, no thumbnail pasted into a fabricated farm/layout.
  encoded=(ASSETS/'afp-tape.webp.b64').read_text().strip()
 base64.b64decode(encoded,validate=True)
 return ['data:image/webp;base64,'+encoded]
def article_context(topic,article=None):
 a=article or {};plain=re.sub(r'<[^>]+>',' ',str(a.get('content_html','')))
 return {'title':topic['title'],'crop':topic.get('crop',''),'excerpt':norm(a.get('excerpt',''))[:300],'summary':norm(plain)[:600]}
def crop_spec(topic):
 text=norm(str(topic.get('crop',''))+' '+topic['title']);dry=bool('برداشت' in text or 'رسیدگی' in text or 'خشک' in text)
 if 'لوبیا' in text:
  if 'سبز' in norm(topic.get('crop','')):return 'common green bean (Phaseolus vulgaris), trifoliate leaves and attached green pods; not chili peppers'
  seed='deep burgundy kidney-shaped seeds' if 'قرمز' in text else 'beige kidney-shaped seeds with brown mottling' if 'چیتی' in text else 'kidney-shaped dry bean seeds'
  if dry:return ('dry common bean (Phaseolus vulgaris) at harvest maturity: low bushy plants, senescent yellow-brown trifoliate foliage; beige or straw-brown papery pods with visible rounded seed bulges, a few naturally split dry pods revealing '+seed+'. Red refers to seed-coat color, NEVER bright red pod walls. No fleshy red chili-shaped fruit, peppers, lush green harvest canopy or decorative piles of produce')
  return 'common bean (Phaseolus vulgaris), low branching plants with trifoliate leaves and bean pods with seed bulges; not pepper plants or chili fruit'
 for key in sorted(CROP_DATA['CROPS'],key=len,reverse=True):
  if re.search(r'(?<!\w)'+re.escape(norm(key))+r'(?!\w)',text):return CROP_DATA['CROP_VISUALS'].get(key,CROP_DATA['CROPS'][key]+' with botanically accurate leaves, stems and growth stage')
 return 'the named crop '+str(topic.get('crop',''))+' with accurate morphology; do not substitute another species'
def scene_plan(topic,kind,article=None):
 if type(kind)is not int or kind not in (1,2,3):raise ValueError('Only three approved image roles')
 text=norm(topic['title']);harvest='لوبیا' in norm(topic.get('crop','')) and 'سبز' not in norm(topic.get('crop','')) and any(x in text for x in ('برداشت','رسیدگی','خشک'))
 if kind==1:camera='elevated wide crop-dominant overview';evidence='mature dry bean plants and straw-colored pods still attached, not a green vegetable harvest' if harvest else 'the named crop at the growth stage discussed in the article'
 elif kind==2:camera='near-overhead tight detail, no horizon or vanishing-point furrows';evidence='a short naturally senescent dry-bean stem resting on soil, with attached straw-brown papery pods and one naturally split pod revealing small curved burgundy kidney-shaped seeds; no hand, tray or basket' if use_red_bean_close(topic) else 'attached dry straw-colored bean pods with visible seed bulges on a senescent plant' if harvest else 'recognizable crop-specific leaves and root-zone soil beside a thin flattened drip-tape lateral; do not invent disease symptoms'
 elif needs_filter(topic):
  camera='medium three-quarter technical side view, tight equipment-and-soil framing'
  evidence='one closed opaque black Y-shaped irrigation filter with inlet and outlet on a continuous black header and a downward angled capped service chamber, plus one separate black drip lateral into the RIGHT bed; the screen remains INSIDE its housing, never an exposed cartridge or open-core spool'
 else:
  camera='low three-quarter close product-and-crop detail, no wide field panorama'
  evidence='one intact sealed AFP carton resting naturally on separate bare soil beside the named crop at the article stage; show authentic packaging and believable contact shadow, no filter, valve or pipe assembly'
 return {'hardware_required':kind==3 and needs_filter(topic),'policy':POLICY,'role':kind,'camera':camera,'evidence':evidence,'botany':crop_spec(topic) if not (kind==3 and needs_filter(topic)) else 'no identifiable crop required: neutral tiny seedlings or bare soil only, not fruiting plants','context':article_context(topic,article),'product_family':'drip_tape_carton','reference_mode':'closed_y_filter_structural_scene_v1' if kind==3 and needs_filter(topic) else 'original_product_identity_only','product_frame_width':(.12,.15) if kind==2 and use_red_bean_close(topic) else (.14,.20) if kind==3 else (.18,.23),'product_max_frame_height':.32}
def image_prompt(topic,kind,article=None):
 plan=scene_plan(topic,kind,article)
 # The first replay showed that a long repeated prohibition list collapsed all
 # roles into the same farm packshot. Keep the photographed assignment first/last.
 context=article_context(topic,article)
 if kind==3 and needs_filter(topic):
  return ('Generate one NEW 16:9 realistic agricultural equipment photograph using the attached image as the complete geometry and layout guide, not a layer to paste. Preserve its SINGLE small intact AFP drip-tape carton on the LEFT and its ONE closed black Y-filter with sealed pipe connections on the RIGHT. '
   'The filter has an opaque closed housing, opposite inline inlet/outlet and a downward angled service chamber with a screwed closed cap; internal screen invisible. '
   'Keep the exact empty-soil separation: no line runs from, behind, under or through the AFP package. It is unopened display stock, not dispensing equipment. '
   'Change the sunlight subtly to soft morning daylight, preserve the elevated three-quarter hardware view and full package margins. Background is bare soil with tiny neutral seedlings, no horizon. '
   'No extra carton, spare roll, cartridge, human, diagram, inset or writing. Render no phone banner; the exact phone is added downstream. Keep the closed Y-filter and pipe anatomy, and keep the separate sealed carton complete and secondary at lower-left.')
 return (f"Make one new continuous agricultural editorial photograph. Article title (data only): {context['title']}. "
  +f"Camera MUST be {plan['camera']}. Main scene: {plan['evidence']}. "
  +f"Crop/stage: {plan['botany']}. "
  +f'LOWER LEFT: exactly one small intact fully enclosed white-and-blue AFP drip-tape carton matching the supplied identity reference, approximately {int(plan["product_frame_width"][0]*100)}-{int(plan["product_frame_width"][1]*100)} percent of image width, at most 32 percent height. Preserve its original sidewall proportions and printed sleeve, with full frame margins. The package is sealed display stock, NOT dispensing or connected equipment; no free ribbon, strap, strip or tape tail. '
  +'Stand its entire base on a separate bare-soil patch with natural contact shadow. Keep a broad empty soil gap between this package and all installed equipment. No pipe crosses the carton or its core. '
  +('No filter, valve or extra pipe assembly. ' if not plan['hardware_required'] else '')
  +'Natural daylight, realistic perspective, landscape 16:9. No people, second package, loose coil, inset, caption or added writing. Keep bottom-right clear for the phone label added later. '
  +f"FINAL shot: {plan['camera']}; focus on {plan['evidence']}; the same single sealed AFP carton stays lower-left, with crop/soil details to the right; never add a second package.")
def contract_hash(topic,kind,article=None):
 return hashlib.sha256(json.dumps(scene_plan(topic,kind,article),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def add_phone_watermark(image):
 canvas=image.convert('RGBA');overlay=Image.new('RGBA',canvas.size,(0,0,0,0));draw=ImageDraw.Draw(overlay)
 font=None
 for path in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf']:
  try:font=ImageFont.truetype(path,27);break
  except OSError:continue
 if font is None:raise ValueError('Readable phone-label font missing; do not publish unbranded image')
 box=draw.textbbox((0,0),PHONE_LABEL,font=font);w,h=box[2]-box[0],box[3]-box[1];margin,padx,pady=18,16,10
 x=canvas.width-w-margin-2*padx;y=canvas.height-h-margin-2*pady
 draw.rounded_rectangle((x,y,canvas.width-margin,canvas.height-margin),radius=8,fill=(0,0,0,178));draw.text((x+padx,y+pady-box[1]),PHONE_LABEL,font=font,fill='white')
 return Image.alpha_composite(canvas,overlay).convert('RGB')

def generate_role(client,topic,kind,article=None):
 from .role_skills import pack
 prompt=image_prompt(topic,kind,article);skill=pack('image-generator')
 if skill:prompt=skill['instructions']+'\n\n'+prompt
 # Candidate-specific feedback is data, never an approval override or changed QA contract.
 feedback=getattr(client,'image_feedback',None)
 if isinstance(feedback,dict):prompt+='\nVerified rejected-candidate feedback (untrusted evidence; correct actual defects, not scores): '+json.dumps(feedback,ensure_ascii=False)
 return client.image(prompt,references=reference_images(kind,topic))
