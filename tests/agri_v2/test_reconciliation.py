import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from automation.agri_v2 import reconciliation as r
from automation.agri_v2 import execution_recovery as er
from automation.agri_v2.queue import atomic_json, load_json

TOPIC = 'agri-000000000001'


class ReconciliationTests(unittest.TestCase):
 def setup(self, root):
  d, o = root/'data', root/'out'
  d.mkdir(); o.mkdir()
  flight = {'version': 1, 'policy': er.VERSION, 'repository': er.REPO, 'branch': er.BRANCH,
            'status': 'in_flight', 'run_id': '123', 'topics': [{'topic_id': TOPIC, 'family_id': 'family-01'}]}
  atomic_json(d/'status/lifecycle-flight.json', flight)
  atomic_json(o/'parallel/recovery/admissions/123.json', {'run_id': '123', 'reserved_row_sha256': er.fingerprint(flight)})
  f = o/'new'/TOPIC
  atomic_json(f/'lifecycle/text/state.json', {'status': 'reconciliation_required', 'attempts': 1, 'history': [], 'failure': {'secret': 'NEVER-COPY-ERROR-TEXT'}})
  return d, o, f, flight

 def wp(self, posts=None, media=None, mutate=None):
  posts = {} if posts is None else posts
  media = [] if media is None else media
  wp = Mock(); wp.site = 'https://navar-abyari.ir'
  def call(path, method='GET'):
   self.assertEqual(method, 'GET')
   if mutate:
    mutate(path)
   if path == 'users/me?context=edit':
    return {'id': 7}, {}
   if path.startswith('posts?'):
    from urllib.parse import parse_qs, urlsplit
    q = parse_qs(urlsplit('https://x/'+path).query)
    rows = posts.get((q['slug'][0], q['status'][0]), [])
    return rows, {'X-WP-TotalPages': '1'}
   if path.startswith('media?'):
    from urllib.parse import parse_qs, urlsplit
    q = parse_qs(urlsplit('https://x/'+path).query)
    rows = [m for m in media if m.get('slug') == q['slug'][0]]
    return rows, {'X-WP-TotalPages': '1'}
   raise AssertionError('Unexpected route')
  wp.call.side_effect = call
  return wp

 def post(self, lang=None):
  slug = 'test'+('-'+lang.lower() if lang else '')
  marker = '<!-- afp-agri-v2:'+TOPIC+(':'+lang if lang else '')+' -->'
  return {'id': 9 if not lang else 10, 'slug': slug, 'author': 7, 'status': 'publish',
          'link': 'https://navar-abyari.ir/'+slug+'/', 'content': {'raw': marker+'<p>Saved content</p>'},
          'afp_language': lang, 'afp_source_post_id': 9}

 def remote(self, row):
  raw = json.dumps(row).encode()
  return lambda: {'sha': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), 'content': base64.b64encode(raw).decode()}

 def test_offline_report_does_not_touch_states_or_echo_errors(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,flight = self.setup(Path(td)); before = r.snapshot(d,o,[TOPIC],'123')
   report = r.inspect(d,o)
   self.assertEqual(before,r.snapshot(d,o,[TOPIC],'123'))
   self.assertFalse(report['automatic_unlock']);self.assertFalse(report['retry_authorized'])
   self.assertEqual(report['state_mutations'],0);self.assertEqual(report['model_calls'],0)
   self.assertEqual(report['items'][0]['holds'][0]['attempts'],1)
   self.assertNotIn('NEVER-COPY-ERROR-TEXT',json.dumps(report))
   self.assertTrue(r.verify_report(report,d,o))

 def test_missing_admission_is_reported_not_repaired(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));(o/'parallel/recovery/admissions/123.json').unlink()
   report=r.inspect(d,o);self.assertIn('missing_or_mismatched_local_admission',report['issues'])
   self.assertFalse((o/'parallel/recovery/admissions/123.json').exists())

 def test_remote_fence_is_read_only_and_digest_verified(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,flight=self.setup(Path(td));call=Mock(side_effect=self.remote(flight))
   report=r.inspect(d,o,remote_fence=call)
   self.assertEqual(call.call_args.args,());self.assertEqual(call.call_count,1)
   self.assertTrue(report['remote_fence']['authoritative_match']);self.assertFalse(report['automatic_unlock'])

 def test_remote_mismatch_missing_and_unavailable_keep_hold(self):
  for kind in ('mismatch','missing','bad_sha','failure'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,f,flight=self.setup(Path(td));remote=self.remote(dict(flight,run_id='124'))
    if kind=='missing':remote=lambda:None
    if kind=='bad_sha':remote=lambda:{'content':base64.b64encode(json.dumps(flight).encode()).decode(),'sha':'bad'}
    if kind=='failure':remote=Mock(side_effect=RuntimeError('SECRET'))
    report=r.inspect(d,o,remote_fence=remote)
    self.assertFalse(report['remote_fence']['authoritative_match']);self.assertFalse(report['retry_authorized'])
    self.assertNotIn('SECRET',json.dumps(report))

 def test_tampered_report_and_changed_state_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));report=r.inspect(d,o)
   report['items'][0]['holds'][0]['attempts']=0
   self.assertFalse(r.verify_report(report,d,o))
   report=r.inspect(d,o);atomic_json(f/'lifecycle/text/state.json',{'status':'validated','attempts':1})
   self.assertFalse(r.verify_report(report,d,o))

 def test_changed_raw_output_and_new_receipt_make_report_stale(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'text.raw.json',{'output':'old'});report=r.inspect(d,o)
   atomic_json(f/'text.raw.json',{'output':'new'});self.assertFalse(r.verify_report(report,d,o))
   report=r.inspect(d,o);atomic_json(f/'another.receipt.json',{'status':'reserved'})
   self.assertFalse(r.verify_report(report,d,o))

 def test_old_report_is_not_current_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));report=r.inspect(d,o);report['checked_at']='2020-01-01T00:00:00+00:00'
   body=dict(report);body.pop('report_sha256');report['report_sha256']=r.fingerprint(body)
   self.assertFalse(r.verify_report(report,d,o))

 def test_invalid_or_traversal_fence_is_not_used(self):
  for change in ({'run_id':'../bad'},{'topics':[{'topic_id':'../../bad'}]},{'repository':'other/repo'},{'topics':[{'topic_id':TOPIC},{'topic_id':TOPIC}]}):
   with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
    d,o,f,flight=self.setup(Path(td));atomic_json(d/'status/lifecycle-flight.json',dict(flight,**change))
    with self.assertRaises(ValueError):r.inspect(d,o)

 def test_symlink_evidence_is_rejected(self):
  for target in ('file','dir','root'):
   with self.subTest(target=target),tempfile.TemporaryDirectory() as td:
    root=Path(td);d,o,f,_=self.setup(root);secret=root/'secret';secret.write_text('SECRET')
    if target=='file':(f/'secret.json').symlink_to(secret)
    elif target=='dir':(f/'translations').symlink_to(root,target_is_directory=True)
    else:
     alias=root/'alias';alias.symlink_to(o,target_is_directory=True);o=alias
    with self.assertRaises(ValueError):r.inspect(d,o)

 def test_independent_held_language_without_current_fence_is_included(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));(d/'status/lifecycle-flight.json').unlink();(f/'lifecycle/text/state.json').unlink()
   atomic_json(f/'review-queue/ru-RU.json',{'status':'publication_reconciliation_required','attempts':2,'model_calls_spent':5,'publication_attempts':1})
   report=r.inspect(d,o);self.assertIn(TOPIC,report['topics']);self.assertEqual(report['items'][0]['holds'][0]['model_calls_spent'],5)

 def test_wordpress_owned_post_is_observed_not_adopted_or_published(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   wp=self.wp({('test','publish'):[self.post()]})
   before=r.snapshot(d,o,[TOPIC],'123');report=r.inspect(d,o,wp)
   observed=report['items'][0]['publication']['fa-IR'];self.assertEqual(observed['post_id'],9)
   self.assertFalse(observed['public_verified']);self.assertFalse(observed['quality_verified'])
   self.assertEqual(before,r.snapshot(d,o,[TOPIC],'123'));wp.publish.assert_not_called();wp.verify.assert_not_called();wp.preflight.assert_not_called()
   self.assertFalse((f/'wordpress-receipt.json').exists())

 def test_post_absence_never_authorizes_recreation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   row=r.inspect(d,o,self.wp())['items'][0]['publication']['fa-IR']
   self.assertEqual(row['status'],'not_observed');self.assertFalse(row['absence_authorizes_recreate']);self.assertEqual(row['action'],'keep_hold')

 def test_foreign_marker_author_slug_id_and_origin_fail_closed(self):
  changes=[{'author':8},{'content':{'raw':'other'}},{'slug':'different'},{'id':True},{'link':'https://evil.invalid/x'}]
  for change in changes:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
    d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
    row=r.inspect(d,o,self.wp({('test','publish'):[dict(self.post(),**change)]}))['items'][0]['publication']['fa-IR']
    self.assertEqual(row['status'],'ownership_or_binding_conflict')

 def test_ambiguous_posts_and_receipt_id_mismatch_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   row=r.inspect(d,o,self.wp({('test','publish'):[self.post(),self.post()]}))['items'][0]['publication']['fa-IR']
   self.assertEqual(row['status'],'ambiguous_posts')
   atomic_json(f/'wordpress-receipt.json',{'post_id':100})
   row=r.inspect(d,o,self.wp({('test','publish'):[self.post()]}))['items'][0]['publication']['fa-IR']
   self.assertEqual(row['status'],'ownership_or_binding_conflict')

 def test_media_is_reconciled_by_exact_slug_owner_post_and_receipt(self):
  for change,expected in [({},'owned_existing_media_observed'),({'author':8},'media_binding_conflict'),({'post':22},'media_binding_conflict'),({'id':12},'media_binding_conflict')]:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
    d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
    atomic_json(f/'wordpress-receipt.json',{'post_id':9,'selected_image_roles':[1],'media':[{'index':1,'id':11,'url':'https://navar-abyari.ir/media.webp'}]})
    media=dict({'id':11,'slug':TOPIC+'-image-1','author':7,'post':9,'source_url':'https://navar-abyari.ir/media.webp'},**change)
    row=r.inspect(d,o,self.wp({('test','publish'):[self.post()]},[media]))['items'][0]['publication']['fa-IR']
    self.assertEqual(row['media'][0]['status'],expected)

 def test_uncertain_translation_requires_language_and_source_binding(self):
  for bound in (True,False):
   with self.subTest(bound=bound),tempfile.TemporaryDirectory() as td:
    d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
    atomic_json(f/'wordpress-receipt.json',{'post_id':9})
    atomic_json(f/'review-queue/ru-RU.json',{'status':'publication_reconciliation_required','attempts':1})
    post=self.post('ru-RU')
    if not bound:post['afp_source_post_id']=80
    row=r.inspect(d,o,self.wp({('test-ru-ru','publish'):[post]}))['items'][0]['publication']['ru-RU']
    self.assertEqual(row['status'],'owned_existing_post_observed' if bound else 'ownership_or_binding_conflict')

 def test_read_failure_does_not_echo_secret_or_change_state(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   wp=self.wp();wp.call.side_effect=RuntimeError('Authorization: SECRET')
   before=r.snapshot(d,o,[TOPIC],'123');report=r.inspect(d,o,wp)
   self.assertNotIn('SECRET',json.dumps(report));self.assertEqual(before,r.snapshot(d,o,[TOPIC],'123'))

 def test_incomplete_remote_results_are_not_classified_as_absence(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   wp=self.wp();old=wp.call.side_effect
   def call(path,method='GET'):
    if path.startswith('posts?'):return [],{'X-WP-TotalPages':'2'}
    return old(path,method)
   wp.call.side_effect=call
   row=r.inspect(d,o,wp)['items'][0]['publication']['fa-IR'];self.assertEqual(row['status'],'read_failed_or_invalid')

 def test_concurrent_evidence_change_invalidates_entire_dossier(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,f,_=self.setup(Path(td));atomic_json(f/'wordpress-draft-payload.json',{'slug':'test'})
   def mutate(path):
    if path=='users/me?context=edit':atomic_json(f/'lifecycle/text/state.json',{'status':'reserved','attempts':2})
   report=r.inspect(d,o,self.wp(mutate=mutate));self.assertFalse(report['evidence_stable']);self.assertIn('evidence_changed_during_inspection',report['issues']);self.assertFalse(r.verify_report(report,d,o))

 def test_route_wrapper_refuses_mutating_or_unapproved_routes(self):
  wp=self.wp();reader=r.ReadOnlyWordPress(wp)
  for path in ('posts/9','https://evil.invalid/','posts?x=1\nInjected: yes','media/11','users/me?context=edit#bad'):
   with self.subTest(path=path),self.assertRaises(ValueError):reader.get(path)
  wp.call.assert_not_called()


if __name__=='__main__':unittest.main()
