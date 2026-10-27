"""Read-only uncertainty dossier. Findings never authorize replay or clear a fence.

No model client, publisher, mutating WordPress call, state update or remote PUT
is reachable here. Hash-bound recommendations are for explicit human review.
"""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

from .queue import DATA, OUT, atomic_json, load_json, safe_id, utcnow, age_hours
from .execution_recovery import VERSION, FLIGHT, fingerprint
from .parallel_control import REPO, BRANCH
from .multilingual import LANGUAGES

POLICY = 'read-only-uncertainty-reconciliation-v1'
HELD = {'reserved', 'reconciliation_required', 'publication_reconciliation_required'}
STATUSES = ('publish', 'draft', 'pending', 'future', 'private')


def sha(blob):
 return hashlib.sha256(blob).hexdigest()


def read_json(path):
 if not path.exists():
  return None
 row = load_json(path)
 if not isinstance(row, dict):
  raise ValueError('Expected evidence object')
 return row


def paths_for(data, out, topics, run):
 # Whole selected families bind counters, rejected attempts, raw outputs and
 # publication evidence, not just the files mentioned by a recommendation.
 paths = [data/'status/lifecycle-flight.json']
 if run:
  paths += [out/'parallel/recovery/admissions'/(run+'.json'),
            out/'parallel/lifecycle/runs'/run/'report.json']
 for topic in topics:
  paths += [data/'briefs'/(topic+'.json')]
  folder = out/'new'/topic
  paths.append(folder)
 return paths


def snapshot(data, out, topics, run):
 evidence = {}
 for base, label in ((data, 'data'), (out, 'out')):
  # Refuse evidence roots with symlink components as well as leaf symlinks.
  if any(p.is_symlink() for p in (base, *base.parents)):
   raise ValueError('Symlink evidence root rejected')
 for path in paths_for(data, out, topics, run):
  base = data if path.is_relative_to(data) else out
  label = 'data' if base == data else 'out'
  nodes = [path] + (sorted(path.rglob('*')) if path.is_dir() else [])
  for node in nodes:
   if node.is_symlink() or any(p.is_symlink() for p in node.parents if p.is_relative_to(base)):
    raise ValueError('Symlink evidence rejected')
   key = label+'/'+node.relative_to(base).as_posix()
   if not node.exists():
    evidence[key] = None
   elif node.is_file():
    h = hashlib.sha256()
    with node.open('rb') as handle:
     for chunk in iter(lambda: handle.read(1024*1024), b''):
      h.update(chunk)
    evidence[key] = h.hexdigest()
   elif not node.is_dir():
    raise ValueError('Nonregular evidence rejected')
   if len(evidence) > 100000:
    raise ValueError('Evidence scope too large')
 return evidence


class ReadOnlyWordPress:
 """GET-only, fixed route boundary; never delegates preflight/publish/verify."""
 def __init__(self, wp):
  if wp.site != 'https://navar-abyari.ir':
   raise ValueError('Unapproved reconciliation origin')
  self.wp, self.requests = wp, 0

 def get(self, path):
  if not re.fullmatch(r'(?:users/me\?context=edit|(?:posts|media)\?[^\r\n#]+)', path):
   raise ValueError('Unapproved read-only route')
  self.requests += 1
  return self.wp.call(path, method='GET')

 def identity(self):
  row, _ = self.get('users/me?context=edit')
  if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0:
   raise ValueError('Invalid authenticated identity')
  return row['id']

 def matches(self, resource, slug, status=None):
  query = resource+'?slug='+quote(slug, safe='')+'&context=edit&per_page=100&page=1'
  if status:
   query += '&status='+status
  rows, headers = self.get(query)
  if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
   raise ValueError('Invalid remote collection')
  pages = next((v for k, v in headers.items() if k.lower() == 'x-wp-totalpages'), None)
  if pages is not None and (not str(pages).isdigit() or int(pages) > 1):
   raise ValueError('Incomplete remote collection')
  if pages is None and len(rows) >= 100:
   raise ValueError('Unproven collection completeness')
  return rows


def remote_publication(reader, owner, topic, folder, language=None):
 payload = read_json(folder/'wordpress-draft-payload.json')
 if not payload or not isinstance(payload.get('slug'), str) or not payload['slug']:
  return {'status': 'missing_local_slug', 'action': 'keep_hold'}
 slug = payload['slug'] + ('-'+language.lower() if language else '')
 marker = '<!-- afp-agri-v2:'+topic+(':'+language if language else '')+' -->'
 receipt = read_json(folder/'translations'/(language+'.wordpress.json') if language else folder/'wordpress-receipt.json') or {}
 source = read_json(folder/'wordpress-receipt.json') or {}
 rows = []
 for status in STATUSES:
  rows.extend(reader.matches('posts', slug, status))
 if len(rows) > 1:
  return {'status': 'ambiguous_posts', 'action': 'keep_hold', 'matches': len(rows)}
 if not rows:
  return {'status': 'not_observed', 'action': 'keep_hold', 'absence_authorizes_recreate': False}
 post = rows[0]
 valid = (type(post.get('id')) is int and post['id'] > 0 and post.get('slug') == slug
          and post.get('author') == owner and type(post.get('author')) is int
          and marker in post.get('content', {}).get('raw', '')
          and post.get('status') in STATUSES)
 if receipt.get('post_id') is not None:
  valid = valid and post['id'] == receipt['post_id']
 if language:
  valid = valid and type(source.get('post_id')) is int and post.get('afp_language') == language and post.get('afp_source_post_id') == source['post_id']
 url = post.get('link', '')
 parts = urlsplit(url)
 valid = valid and parts.scheme == 'https' and parts.netloc == 'navar-abyari.ir' and not parts.fragment
 if not valid:
  return {'status': 'ownership_or_binding_conflict', 'action': 'keep_hold'}
 result = {'status': 'owned_existing_post_observed', 'post_id': post['id'],
           'post_status': post['status'], 'action': 'review_existing_post_no_repost',
           'public_verified': False, 'quality_verified': False, 'media': []}
 roles = source.get('selected_image_roles', [1, 2])
 if roles not in ([1], [2], [1, 2]):
  return {'status': 'invalid_media_selection', 'action': 'keep_hold'}
 expected_media = source.get('media', [])
 for role in roles:
  expected_slug = topic+'-image-'+str(role)
  found = reader.matches('media', expected_slug)
  item = {'role': role, 'status': 'not_observed'}
  if len(found) > 1:
   item['status'] = 'ambiguous_media'
  elif found:
   media = found[0]
   known = [m for m in expected_media if m.get('index') == role]
   valid_media = (type(media.get('id')) is int and media['id'] > 0
                  and media.get('slug') == expected_slug and media.get('author') == owner
                  and type(media.get('author')) is int
                  and media.get('post') in (0, source.get('post_id', post['id'])))
   if known:
    valid_media = valid_media and len(known) == 1 and media['id'] == known[0].get('id') and media.get('source_url') == known[0].get('url')
   item.update(status='owned_existing_media_observed' if valid_media else 'media_binding_conflict')
   if valid_media:
    item['media_id'] = media['id']
  result['media'].append(item)
 if any(m['status'] != 'owned_existing_media_observed' for m in result['media']):
  result['action'] = 'keep_hold_review_media'
 # Existence is never a quality verdict or proof of a finished publication.
 return result


def inspect(data=DATA, out=OUT, wp=None, remote_fence=None):
 data, out = Path(data), Path(out)
 # Check roots before reading the fence.
 snapshot(data, out, [], '')
 flight = read_json(data/'status/lifecycle-flight.json')
 run, topics, issues = '', [], []
 if flight:
  if (flight.get('version') != 1 or flight.get('policy') != VERSION
      or flight.get('repository') != REPO or flight.get('branch') != BRANCH
      or not re.fullmatch(r'[0-9]+', str(flight.get('run_id', '')))
      or flight.get('status') not in ('in_flight', 'checkpointed')):
   raise ValueError('Invalid lifecycle fence; no reconciliation scope inferred')
  run = str(flight['run_id'])
  entries = flight.get('topics')
  if not isinstance(entries, list) or not 1 <= len(entries) <= 20:
   raise ValueError('Invalid fence topics')
  for item in entries:
   safe_id(item['topic_id']); topics.append(item['topic_id'])
  if len(topics) != len(set(topics)):
   raise ValueError('Duplicate fence topics')
 # Include held families no longer active (independent language backlog).
 for p in sorted((out/'new').glob('agri-*')):
  safe_id(p.name)
  if p.is_symlink():
   raise ValueError('Symlink family rejected')
  held = list(p.glob('lifecycle/*/state.json')) + list(p.glob('review-queue/*.json'))
  for state in held:
   if state.is_symlink() or any(a.is_symlink() for a in state.parents if a.is_relative_to(out)):
    raise ValueError('Symlink state rejected')
   row = read_json(state)
   if row and row.get('status') in HELD and p.name not in topics:
    topics.append(p.name)
 before = snapshot(data, out, topics, run)
 if flight and flight['status'] == 'in_flight':
  issues.append('in_flight_run_requires_review')
 admission = read_json(out/'parallel/recovery/admissions'/(run+'.json')) if run else None
 if flight and flight['status'] == 'in_flight' and (not admission or admission.get('run_id') != run or admission.get('reserved_row_sha256') != fingerprint(flight)):
  issues.append('missing_or_mismatched_local_admission')
 remote = {'status': 'not_checked', 'authoritative_match': False}
 if remote_fence is not None:
  try:
   found = remote_fence()
   raw = base64.b64decode(found['content'], validate=False)
   row = json.loads(raw)
   blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
   matches = (found.get('sha') == blob and row == flight and row.get('repository') == REPO and row.get('branch') == BRANCH)
   remote = {'status': 'matches_local' if matches else 'mismatch', 'authoritative_match': matches, 'blob_sha': blob}
   if not matches:
    issues.append('remote_fence_mismatch')
  except Exception:
   remote = {'status': 'unavailable_or_invalid', 'authoritative_match': False}
   issues.append('remote_fence_unavailable')
 reader, owner = None, None
 wp_status = 'not_requested'
 if wp is not None:
  try:
   reader = ReadOnlyWordPress(wp); owner = reader.identity(); wp_status = 'authenticated_get_only'
  except Exception:
   wp_status = 'unavailable_or_invalid'; issues.append('wordpress_identity_unavailable'); reader = None
 items = []
 for topic in topics:
  folder = out/'new'/topic
  item = {'topic_id': topic, 'holds': [], 'publication': {}}
  for path in sorted(folder.glob('lifecycle/*/state.json')) + sorted(folder.glob('review-queue/*.json')):
   row = read_json(path)
   if not row or row.get('status') not in HELD:
    continue
   held = {'path': path.relative_to(out).as_posix(), 'status': row['status'],
           'attempts': row.get('attempts'), 'model_calls_spent': row.get('model_calls_spent'),
           'publication_attempts': row.get('publication_attempts'), 'action': 'keep_hold_review_saved_evidence'}
   # No raw/error/provider text is copied to the report.
   held['state_sha256'] = before['out/'+held['path']]
   item['holds'].append(held)
  receipts = sorted(folder.rglob('*.receipt.json'))
  item['request_receipts'] = [{'path': p.relative_to(out).as_posix(), 'sha256': before['out/'+p.relative_to(out).as_posix()]} for p in receipts]
  targets = []
  if (folder/'wordpress-draft-payload.json').exists():
   targets.append(None)
   for lang in LANGUAGES:
    state = read_json(folder/'review-queue'/(lang+'.json')) or {}
    if state.get('status') == 'publication_reconciliation_required' or (folder/'translations'/(lang+'.wordpress.json')).exists():
     targets.append(lang)
  for language in targets:
   key = language or 'fa-IR'
   if reader is None:
    item['publication'][key] = {'status': 'not_checked', 'action': 'keep_hold'}
   else:
    try:
     item['publication'][key] = remote_publication(reader, owner, topic, folder, language)
    except Exception:
     item['publication'][key] = {'status': 'read_failed_or_invalid', 'action': 'keep_hold'}
  items.append(item)
 after = snapshot(data, out, topics, run)
 stable = before == after
 if not stable:
  issues.append('evidence_changed_during_inspection')
 report = {'version': 1, 'policy': POLICY, 'checked_at': utcnow(),
           'repository': REPO, 'branch': BRANCH, 'run_id': run or None,
           'status': 'review_required' if issues or any(i['holds'] for i in items) else 'observations_only',
           'issues': issues, 'topics': topics, 'items': items, 'evidence_stable': stable,
           'evidence': before, 'evidence_sha256': fingerprint(before), 'remote_fence': remote,
           'wordpress': {'status': wp_status, 'get_requests': reader.requests if reader else 0},
           'model_calls': 0, 'post_mutations': 0, 'state_mutations': 0,
           'automatic_unlock': False, 'retry_authorized': False, 'publication_authorized': False,
           'review_steps': ['Compare current authoritative fence and digest-bound evidence.',
                            'Inspect saved outputs and provider-side receipts; absence is not non-execution proof.',
                            'Reconcile actual owned WordPress posts/media; never recreate solely on absence.',
                            'Keep unknown outcomes held; any state adoption requires a separate reviewed change preserving counters.']}
 report['report_sha256'] = fingerprint(report)
 return report


def verify_report(report, data=DATA, out=OUT):
 """Refuse stale/tampered dossiers; this returns no permission to mutate."""
 try:
  body = dict(report); expected = body.pop('report_sha256')
  if report.get('policy') != POLICY or fingerprint(body) != expected or not report.get('evidence_stable'):
   return False
  if not 0 <= age_hours(report['checked_at']) <= 0.25:
   return False
  for topic in report['topics']:
   safe_id(topic)
  run = report['run_id'] or ''
  if run and not re.fullmatch(r'[0-9]+', run):
   return False
  return snapshot(Path(data), Path(out), report['topics'], run) == report['evidence']
 except (ValueError, KeyError, TypeError, OSError):
  return False


def main():
 parser = argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--wordpress-read-only', action='store_true')
 parser.add_argument('--remote-fence-read-only', action='store_true')
 args = parser.parse_args()
 wp = None; remote = None
 if args.wordpress_read_only:
  from .wordpress import WordPress
  wp = WordPress()
 if args.remote_fence_read_only:
  import os
  from .execution_recovery import transport
  remote = lambda: transport(os.environ, 'GET')
 report = inspect(wp=wp, remote_fence=remote)
 # Only a new diagnostic artifact is written; no states/receipts/fences change.
 dest = OUT/'parallel/recovery/reconciliation/latest.json'
 atomic_json(dest, report)
 print(json.dumps({k: report[k] for k in ('status', 'run_id', 'issues', 'evidence_stable', 'report_sha256', 'model_calls', 'post_mutations', 'state_mutations')}, ensure_ascii=False))
 return 0 if report['evidence_stable'] else 2


if __name__ == '__main__':
 raise SystemExit(main())
