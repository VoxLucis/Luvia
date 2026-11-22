#!/usr/bin/env python3
"""Apply one explicitly approved headline candidate as a human-reviewed milestone."""
import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
PID = os.environ.get('FAB_PROPOSAL_ID', '').strip()
STAGE = os.environ.get('FAB_APPROVED_STAGE', '保持原階段').strip()
NOTE = os.environ.get('FAB_VERIFICATION_NOTE', '').strip()
REVIEWER = os.environ.get('FAB_REVIEWER', '').strip()
STAGES = {'保持原階段', '規劃中', '建設中', '設備進駐', '試產中', '量產中', '延期／調整'}
if not PID or STAGE not in STAGES or len(NOTE) < 15 or len(NOTE) > 600 or not REVIEWER:
    raise SystemExit('Missing proposal ID, valid stage, reviewer, or substantive verification note (15–600 chars).')

proposal_path = DATA / 'fab_proposals.json'
fab_path = DATA / 'fabs.json'
proposals = json.loads(proposal_path.read_text(encoding='utf-8'))
fabs = json.loads(fab_path.read_text(encoding='utf-8'))
candidate = next((p for p in proposals.get('proposals', []) if p.get('id') == PID), None)
if not candidate or candidate.get('status') != 'pending':
    raise SystemExit('Proposal is missing or already reviewed: ' + PID)
project = next((p for p in fabs.get('projects', []) if p.get('id') == candidate.get('project_id')), None)
if not project:
    raise SystemExit('Fab project not found; cannot apply: ' + PID)
if not str(candidate.get('source_url', '')).startswith('https://'):
    raise SystemExit('Candidate lacks an HTTPS source; cannot apply.')

review_date = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
milestone_stage = project.get('stage', '待確認') if STAGE == '保持原階段' else STAGE
milestones = project.setdefault('milestones', [])
if any(x.get('candidate_id') == PID for x in milestones):
    raise SystemExit('Already included in milestone history.')
milestones.append({
    'date': candidate.get('source_date', review_date),
    'stage': milestone_stage,
    'title': candidate['title'][:200],
    'source_url': candidate['source_url'],
    'source_type': '公開新聞（人工閱讀查核；非官方公告）',
    'reviewed_by': REVIEWER,
    'reviewed_at': review_date,
    'verification_note': NOTE,
    'candidate_id': PID
})
if STAGE != '保持原階段':
    project['stage'] = STAGE
    project['summary'] = '人工核對的進度更新：' + NOTE[:250]
    project['verified_date'] = candidate.get('source_date', review_date)
    project['update_date'] = review_date
    project['evidence'] = '人工審核的新聞來源（非官方證實）'
    project['source_url'] = candidate['source_url']
    project['source_title'] = candidate['title'][:160]
candidate['status'] = 'approved'
candidate['approved_at'] = review_date
candidate['approved_stage'] = STAGE
candidate['reviewed_by'] = REVIEWER
candidate['verification_note'] = NOTE
fabs['as_of'] = review_date
fab_path.write_text(json.dumps(fabs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
proposal_path.write_text(json.dumps(proposals, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Approved', PID, 'for', project['id'], 'stage:', STAGE)
