#!/usr/bin/env python3
"""Explicit human review via restricted GitHub Actions workflow_dispatch."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,urllib.parse

DATA=Path(__file__).resolve().parent/'data'
def load(name):return json.loads((DATA/name).read_text(encoding='utf-8'))
def save(name,value):(DATA/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    candidate_id=os.environ.get('CAPABILITY_ID','').strip()
    decision=os.environ.get('CAPABILITY_DECISION','').strip()
    note=os.environ.get('CAPABILITY_REVIEW_NOTE','').strip()
    product=os.environ.get('CAPABILITY_PRODUCT','').strip()
    reviewer=os.environ.get('GITHUB_ACTOR','').strip()
    owner=os.environ.get('REPOSITORY_OWNER','').strip()
    if not reviewer or not owner or reviewer.casefold()!=owner.casefold():raise SystemExit('Only repository owner may approve or reject.')
    if decision not in ('approve','reject'):raise SystemExit('Decision must be approve/reject')
    if not candidate_id.startswith('cap-') or len(note)<15 or len(note)>800:raise SystemExit('ID or substantive human verification note missing (15–800 chars)')
    if len(product)>150:raise SystemExit('Product name too long')
    doc=load('capability_candidates.json')
    candidate=next((x for x in doc.get('candidates',[]) if x.get('id')==candidate_id),None)
    if not candidate or candidate.get('status')!='pending':raise SystemExit('Candidate missing or already reviewed')
    matrix=load('equipment_matrix.json')
    allowed={t['id'] for t in matrix.get('technologies',[])}
    if candidate['technology'] not in allowed:raise SystemExit('Unknown technology')
    firm=next((x for x in matrix.get('companies',[]) if x.get('name')==candidate['company']),None)
    if not firm:raise SystemExit('Company not registered in approved matrix')
    url=candidate.get('url','')
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:raise SystemExit('Official HTTPS URL required')
    if len(candidate.get('excerpt',''))<20:raise SystemExit('Original quote missing')
    today=datetime.now(timezone.utc).date().isoformat()
    if decision=='approve':
        # Reviewer must explicitly state a human reading of the official source;
        # a model's proposed product name alone is not sufficient for approval.
        if not product:raise SystemExit('Give the verified product/platform name, or "官方產品頁" if none is stated')
        if candidate['technology'] in firm.setdefault('evidence',{}) and firm['evidence'][candidate['technology']].get('status')=='verified':
            raise SystemExit('Already has a verified claim; review manually before replacing it')
        firm['evidence'][candidate['technology']]={'status':'verified','date':today,'product':product,
            'note':note,'url':url,'source_type':'official_product_or_release',
            'quote':candidate['excerpt'],'reviewed_by':reviewer,'candidate_id':candidate_id}
        matrix['updated_at']=today
        save('equipment_matrix.json',matrix)
    candidate.update(status=('approved' if decision=='approve' else 'rejected'),reviewer=reviewer,reviewed_at=today,review_note=note)
    doc['updated_at']=datetime.now(timezone.utc).isoformat()
    save('capability_candidates.json',doc)
    history_file=DATA/'capability_review_history.json'
    try:history=load('capability_review_history.json')
    except (OSError,ValueError):history={'schema_version':1,'reviews':[]}
    history['reviews'].append({'id':candidate_id,'company':candidate['company'],'technology':candidate['technology'],'decision':decision,'reviewed_at':today,'reviewer':reviewer,'note':note,'source_url':url})
    save('capability_review_history.json',history)
    print('Human review completed:',decision,candidate_id)
if __name__=='__main__':main()
