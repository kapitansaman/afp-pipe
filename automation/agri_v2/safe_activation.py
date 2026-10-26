"""Explicit source-ready activation only after a current canary and agent inspection.
Never clears a topic hold, skips image QA, or resets an exhausted retry budget.
"""
import hashlib
from .queue import DATA,OUT,ROOT,load_json,get_topic
from .image_quality import valid_record,REVIEW_POLICY,SCORE_POLICY
from .healthcheck import IMAGE_MODEL
OWNER_ID='owner-practical85-source-ready-activation-v1'
ID='one-hour-source-ready-activation-v1';TOPIC='agri-af1a4b491d83'
def authorized(data_path=None):
 data=DATA if data_path is None else data_path
 path=data/'safe-activation-request.json'
 if not path.exists():return False
 req=load_json(path)
 if req.get('request_id')=='afp-pipe-controlled-start-v1':
  from .controlled_start import authorized as controlled_authorized
  return controlled_authorized(req,data,OUT,ROOT)
 if req.get('request_id')==OWNER_ID:return owner_authorized(req,data)
 if req.get('request_id')!=ID or req.get('authorized') is not True or req.get('mode')!='source_ready_quality_gated_only' or req.get('max_posts_per_run')!=1 or req.get('preserve_publication_holds') is not True:raise ValueError('Exact safe source-ready activation required')
 config=load_json(data/'config.json')
 if TOPIC not in config.get('publication_holds',{}) or config.get('max_posts_per_run')!=1:raise ValueError('Pilot hold and single-post bound must remain')
 report_path=OUT/'health-canary/one-hour-final-technical-canary-v1/report.json'
 if hashlib.sha256(report_path.read_bytes()).hexdigest()!=req['canary_report_sha256']:raise ValueError('Canary report changed')
 report=load_json(report_path)
 if report.get('status')!='candidate_requires_agent_visual_review' or report.get('automated_pass') is not True or report.get('valid_image_bytes') is not True or report.get('post_mutations')!=0:raise ValueError('No successful bounded technical canary')
 image=report_path.with_name('role-3.webp')
 if report.get('path')!=str(image.relative_to(ROOT)):raise ValueError('Unexpected canary image path')
 topic=get_topic('new',TOPIC);article=load_json(OUT/'new'/TOPIC/'article.json');valid_record(image,topic,3,article)
 image_sha=hashlib.sha256(image.read_bytes()).hexdigest()
 agent_path=report_path.with_name('agent-visual-review.json')
 if hashlib.sha256(agent_path.read_bytes()).hexdigest()!=req['agent_review_sha256']:raise ValueError('Agent inspection changed')
 agent=load_json(agent_path)
 if agent.get('image_sha256')!=image_sha or agent.get('canary_visual_pass') is not True or agent.get('human_review_claimed') is not False or agent.get('pilot_publication_approved') is not False:raise ValueError('Independent canary inspection missing or approval scope wrong')
 health=load_json(data/'health/latest.json')
 if health.get('image_model')!=IMAGE_MODEL or not health.get('eligible_image_slots'):raise ValueError('No matching image capability pool')
 return True

def skip_completed_tuning():
 request=load_json(DATA/'image-tuning-resume-request.json');report=OUT/'image-backtests'/request['backtest_request_id']/'report.json'
 if not report.exists():return False
 return load_json(report).get('status') not in (None,'reserved')


def owner_authorized(req,data):
 # Owner authorizes starting the normal pipeline, NOT approving the failed canary.
 if (req.get('authorized') is not True or req.get('mode')!='source_ready_critical_checks'
     or req.get('score_policy')!='advisory_only' or SCORE_POLICY!='advisory_only'
     or req.get('review_policy')!=REVIEW_POLICY or req.get('max_posts_per_run')!=1
     or req.get('preserve_publication_holds') is not True):raise ValueError('Explicit owner quality policy authorization required')
 config=load_json(data/'config.json')
 if TOPIC not in config.get('publication_holds',{}) or config.get('max_posts_per_run')!=1:raise ValueError('Pilot hold and single-post bound must remain')
 if config.get('automatic_generation') is not True or config.get('publication_enabled') is not True:raise ValueError('Generator not enabled')
 report_path=OUT/'activation-health/one-hour-activation-health-v1/report.json'
 if hashlib.sha256(report_path.read_bytes()).hexdigest()!=req.get('readiness_report_sha256'):raise ValueError('Readiness proof changed')
 report=load_json(report_path)
 if (report.get('article_validation_passed') is not True or report.get('post_mutations')!=0
     or report.get('wordpress_connection',{}).get('can_publish') is not True):raise ValueError('Missing source and connection readiness proof')
 health=load_json(data/'health/latest.json')
 if health.get('image_model')!=IMAGE_MODEL or not health.get('eligible_image_slots'):raise ValueError('No matching image capability pool')
 # Normal cycle still rechecks freshness, inventory, source brief and both production images.
 return True
