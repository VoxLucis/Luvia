#!/usr/bin/env python3
"""Discover fab-specific RSS headlines and propose review-only changes.

This is NOT a primary-source fact checker. No edits to data/fabs.json.
"""
import datetime as dt
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime.now(TZ)
FAB = json.loads((DATA / 'fabs.json').read_text(encoding='utf-8'))
PROPOSALS_PATH = DATA / 'fab_proposals.json'
PREVIOUS = json.loads(PROPOSALS_PATH.read_text(encoding='utf-8')) if PROPOSALS_PATH.exists() else {'proposals': []}

# A deliberately narrow query + a mandatory location anchor per project.
# Adjust entries as additional fabs are added; unknown fabs are reported, not guessed.
QUERIES = {
    'tsmc-az-fab2': ('TSMC Arizona second fab equipment installation production', ['arizona', 'phoenix', '亞利桑那'], ['tsmc', '台積電']),
    'tsmc-jasm-fab2': ('TSMC JASM Kumamoto second fab construction production', ['kumamoto', '熊本', 'jasm'], ['tsmc', '台積電', 'jasm']),
    'tsmc-tainan-n3': ('TSMC Tainan new 3nm fab expansion construction', ['tainan', '台南'], ['tsmc', '台積電']),
    'ase-kaohsiung-new': ('ASE Kaohsiung new advanced packaging factory construction', ['kaohsiung', '高雄'], ['ase', '日月光']),
    'ase-renwu': ('ASE Renwu testing park phase two construction', ['renwu', '仁武'], ['ase', '日月光']),
    'intel-ohio-one': ('Intel Ohio One fab construction schedule', ['ohio', '俄亥俄'], ['intel', '英特爾']),
}
# Some seed project ids may differ; fallback is visible in scan report.
project_by_id = {p['id']: p for p in FAB['projects']}


def check_anchor(title, terms):
    low = title.lower()
    return any(t.lower() in low for t in terms)


# Conservative lexical screen. A company+location match alone is NOT a milestone.
FINANCE_NOISE = re.compile(r"stock|share price|price target|analyst|earnings|net income|profit|dividend|revenue|market cap|shares|forecast stock|financial results|股價|股票|財報|營收|獲利|淨利|法人|目標價|投資評級", re.I)
MILESTONE = re.compile(r"breaks? ground|groundbreaking|construction|under construction|build(?:ing)? (?:a |the )?(?:new )?(?:fab|plant|facility)|facility opening|plant opening|opened (?:a |the )?(?:plant|fab)|equipment (?:move.?in|installation|installed)|tool installation|pilot production|trial production|mass production|volume production|production start|ramp(?:ing)? up|delay(?:ed)?|postpon(?:e|ed)|schedule revised|inaugurat|completion|commissio|動土|開工|興建|建廠|廠房|新廠啟用|設備進駐|裝機|機台搬入|試產|量產|投產|啟用|延期|延後|竣工|完工",re.I)
# Headline screening remains a heuristic; source article verification remains mandatory.
def headline_relevant(title):
    if FINANCE_NOISE.search(title) and not MILESTONE.search(title):
        return False
    return bool(MILESTONE.search(title))

def collect():
    items = []
    issues = []
    scanned = 0
    filtered = 0
    for project in FAB['projects']:
        cfg = QUERIES.get(project['id'])
        if not cfg:
            issues.append('尚未設定廠區專屬搜尋：' + project['id'])
            continue
        query, places, companies = cfg
        params = urllib.parse.urlencode({'q': query + ' when:21d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        url = 'https://news.google.com/rss/search?' + params
        scanned += 1
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 Semicon-Fab-Milestone/4.1'})
            with urllib.request.urlopen(req, timeout=20) as response:
                root = ET.fromstring(response.read())
            for node in root.findall('./channel/item')[:35]:
                title = unescape(re.sub('<[^>]+>', '', node.findtext('title', '')).strip())
                link = node.findtext('link', '').strip()
                if not title or not link or not check_anchor(title, places) or not check_anchor(title, companies):
                    continue
                if not headline_relevant(title):
                    filtered += 1
                    continue
                try:
                    date = email.utils.parsedate_to_datetime(node.findtext('pubDate', '')).date()
                except (TypeError, ValueError):
                    continue
                if not 0 <= (NOW.date() - date).days <= 30:
                    continue
                source_el = node.find('source')
                source = source_el.text.strip() if source_el is not None and source_el.text else 'Google News RSS'
                pid = hashlib.sha256((project['id'] + '|' + title.casefold()).encode('utf-8')).hexdigest()[:16]
                items.append({'id': pid, 'project_id': project['id'], 'project_name': project['name'],
                              'current_stage': project.get('stage', ''), 'current_summary': project.get('summary', ''),
                              'latest_verified': project.get('verified_date', ''), 'title': title,
                              'source_date': date.isoformat(), 'source_url': link, 'source_name': source})
        except (OSError, ValueError, ET.ParseError) as exc:
            issues.append(project['name'] + ': RSS 擷取失敗 ' + type(exc).__name__)
    return items, scanned, issues, filtered


def compare_ai(items):
    """Outputs AI annotations only for the same ids; never fabricates sources."""
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key or not items:
        return {}, 'AI 未執行（無 Key 或無候選），保留標題待審核'
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    instructions = (
        '你是半導體廠區追蹤編輯。輸入僅有RSS標題、日期及現有正式廠區階段，沒有原文內容。'
        '務必以合法 json 物件回覆，格式為 {"items":[{"id":"候選id",'
        '"comparison":"最多90字，指出標題和現有狀態的差異/不確定性",'
        '"proposed_stage":"保持原階段/規劃中/建設中/設備進駐/試產中/量產中/延期／調整",'
        '"relevance":"高/中/低"}]}。'
        '不可聲稱已核實，也不能自行確認量產、訂單、廠址或時程。'
        '若標題不能證明階段變化，必須寫保持原階段。只回覆收到的候選id。'
    )
    payload = {
        'model': model,
        'instructions': instructions,
        'input': '請以 json 回覆這些未查核新聞候選：' + json.dumps(items[:25], ensure_ascii=False),
        'max_output_tokens': 4500,
        'text': {'format': {'type': 'json_object'}},
    }
    request = urllib.request.Request('https://api.openai.com/v1/responses',
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                                     method='POST')
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.load(response)
        chunks = [part.get('text', '') for item in raw.get('output', [])
                  for part in item.get('content', []) if part.get('type') == 'output_text']
        doc = json.loads(''.join(chunks))
        allowed_ids = {i['id'] for i in items[:25]}
        allowed_stages = {'保持原階段', '規劃中', '建設中', '設備進駐', '試產中', '量產中', '延期／調整'}
        result = {}
        for entry in doc.get('items', []):
            if not isinstance(entry, dict) or entry.get('id') not in allowed_ids:
                continue
            stage = entry.get('proposed_stage', '保持原階段')
            result[entry['id']] = {
                'comparison': str(entry.get('comparison', ''))[:300],
                'proposed_stage': stage if stage in allowed_stages else '保持原階段',
                'ai_status': 'AI初步比對（未查核）',
                'relevance': entry.get('relevance', '中') if entry.get('relevance') in ['高', '中', '低'] else '中'
            }
        return result, 'AI 比對完成（僅標題層級，須人工查證）'
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        # Do not fail the news workflow or lie about having completed AI interpretation.
        print('Fab AI compare not available:', type(exc).__name__, str(exc)[:250])
        return {}, 'AI 判讀未完成；保留來源標題待人工核對'


def main():
    candidates, scanned, issues, filtered = collect()
    print('Scanned projects:', scanned, 'headline candidates:', len(candidates), 'filtered irrelevant:', filtered, 'warnings:', len(issues))
    for warning in issues:
        print('Warning:', warning)
    annotations, ai_status = compare_ai(candidates)
    existing = {x['id']: x for x in PREVIOUS.get('proposals', []) if isinstance(x, dict) and x.get('id')}
    new_count = 0
    for item in candidates:
        if item['id'] in existing:
            continue
        note = annotations.get(item['id'], {})
        # Limit the first release to a manageable human review queue.
        existing[item['id']] = {**item,
            'status': 'pending', 'first_seen': NOW.isoformat(),
            'comparison': note.get('comparison', '只有標題線索，尚無法確認是否超越既有里程碑。'),
            'proposed_stage': note.get('proposed_stage', '保持原階段'),
            'ai_status': note.get('ai_status', '未完成AI判讀'),
            'relevance': note.get('relevance', '待審核')}
        new_count += 1
    pending = sorted((p for p in existing.values() if p.get('status') == 'pending'),
                     key=lambda x: (x.get('source_date', ''), x.get('id', '')), reverse=True)
    approved = [p for p in existing.values() if p.get('status') == 'approved']
    denied = [p for p in existing.values() if p.get('status') == 'rejected']
    # Retain recent reviewed candidates for transparency.
    output = {'updated_at': NOW.isoformat(),
              'scan_status': f'{scanned} 個廠區已執行搜尋；雜訊排除 {filtered} 則；新增 {new_count} 筆；{ai_status}；RSS 警告 {len(issues)} 項',
              'warnings': issues[:20],
              'proposals': pending[:120] + approved[-60:] + denied[-30:]}
    PROPOSALS_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Pending review:', len(pending), 'New:', new_count)

if __name__ == '__main__':
    main()
