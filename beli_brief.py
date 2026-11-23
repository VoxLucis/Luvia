#!/usr/bin/env python3
"""Public-signal-only weekly V5 decision cover.
No private sales, customer, or technical data is sent to the API.
AI suggestions remain hypotheses and never establish customer demand or orders.
"""
import datetime as dt
import json
import os
import pathlib
import re
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'data/beli_brief.json'
TZ = dt.timezone(dt.timedelta(hours=8))

FOCUS = {
    'customer_segments': ['晶圓代工', '封裝測試', '先進封裝'],
    'topics_to_watch': ['ADC / AI 缺陷分類', 'AOI / 外觀檢測', 'JEDEC tray / 六面檢測',
                        '3D 量測', 'X-ray / CT', 'CSAM / SAM', '設備驗證與導入時程'],
    'note': '以上僅是研究關注方向，不代表倍利已具備全部能力、已有客戶採購意願或任何未公開專案進度。'
}

KEYWORDS = ['inspect','inspection','defect','metrology','vision','machine learning',
            'packaging','advanced packaging','aoi','adc','tray','six-sided','6-sided',
            'x-ray','csam','sam','cavity','wafer','hbm','co-wos','cowos','fab',
            'capex','expansion','yield','tool move','semiconductor equipment',
            '檢測','量測','缺陷','封裝','擴廠','晶圓','良率','資本支出','導入','設備']
FINANCE_NOISE = ['stock price','stock forecast','shares','stock analyst','tradingview',
                 'stock to buy','share price','stock picks','股價','股票','投資評級']


def load_candidates():
    news = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))
    today = dt.datetime.now(TZ).date()
    rows = []
    seen = set()
    for item in news.get('items', []):
        if not isinstance(item, dict):
            continue
        try:
            day = dt.date.fromisoformat(str(item.get('date', ''))[:10])
        except ValueError:
            continue
        if not (today - dt.timedelta(days=30) <= day <= today):
            continue
        title = str(item.get('title') or '').strip()
        ident = str(item.get('id') or '')
        url = str(item.get('url') or '').strip()
        if not title or not ident or not url or ident in seen or len(title) < 15:
            continue
        seen.add(ident)
        low = title.casefold()
        score = sum(3 for kw in KEYWORDS if kw in low) - sum(7 for kw in FINANCE_NOISE if kw in low)
        if score <= 0:
            continue
        rows.append({
            'id': ident, 'title': title[:250], 'url': url, 'date': day.isoformat(),
            'company': str(item.get('company') or '')[:100],
            'category': str(item.get('category') or '')[:100],
            'source': str(item.get('source') or '')[:100], 'score': score
        })
    rows.sort(key=lambda x: (x['score'], x['date']), reverse=True)
    # Diverse inputs across companies and topics, avoid one company drowning the report.
    selection, count_by_company = [], {}
    for item in rows:
        company = item['company'] or '產業新聞'
        if count_by_company.get(company, 0) >= 5:
            continue
        selection.append({k:v for k,v in item.items() if k != 'score'})
        count_by_company[company] = count_by_company.get(company, 0) + 1
        if len(selection) >= 35:
            break
    return selection


def source_links(ids, source_by_id):
    result = []
    for ident in ids if isinstance(ids, list) else []:
        s = source_by_id.get(str(ident))
        if s and all(x['id'] != s['id'] for x in result):
            result.append({k: s[k] for k in ('id','title','url','date','source')})
        if len(result) >= 3:
            break
    return result


def clean(text, limit=300):
    return str(text or '').strip()[:limit]


def main():
    key = os.environ.get('OPENAI_API_KEY','').strip()
    if not key:
        print('Beli brief: OPENAI_API_KEY absent. Existing report left unchanged.')
        return
    candidates = load_candidates()
    if len(candidates) == 0:
        print('Beli brief: no relevant recent headlines. Existing report left unchanged.')
        return
    model = os.environ.get('OPENAI_MODEL','gpt-4.1-mini')
    instructions = '''你是倍利科技的「公開產業情報」分析編輯。你只知道以下公開研究關注方向，不知道倍利的內部產品型錄、供貨能力、客戶名單、合作關係或未公開專案。輸入僅是新聞標題／來源中繼資料；沒有閱讀文章全文！
請輸出單一合法 json 物件，不要 markdown。必須長得像：
{"priorities":[{"headline":"20字內標題","company":"公司名","priority":"高/中/低","impact_type":"商機線索/競爭觀察/供應鏈風險/政策風險/技術趨勢","evidence_summary":"僅根據標題的事實線索，不得宣稱已查證","beli_implication":"對倍利可能意義，必須標為推論或假設","next_check":"可操作、具體的一項查證問題","evidence_level":"僅新聞標題，未查證","source_ids":["候選新聞id"]}],"actions":[{"priority":"本週優先/持續追蹤","owner_suggestion":"業務/FAE/PM/研發/管理層（僅建議角色）","question":"待確認的具體問題","why":"為何需要確認，基於哪類公開訊號"}],"risks":[{"level":"高/中/低","title":"風險名稱","detail":"風險與未知事項，不能斷言已發生"}]}
重點：選 3-5 個「不同事件」的優先訊號；排除純股價、股市行情、投資推薦與重複報導，優先擴廠里程碑、設備需求、先進封裝、ADC、AOI、Tray、競品產品與政策。至少每個 priority 有 1 個來源 id，必須完全等於輸入中的 id，不能編造來源；不要複製長篇新聞文字。actions 3-6 項、risks 1-4 項。不要把設備需求假設寫成已取得訂單，不要聲稱倍利現有技術規格、客戶認證或客戶採購。所謂「需確認」是確認方向，不是待完成的內部承諾。'''
    payload = {
        'model':model,
        'instructions':instructions,
        'input':'請用 json 格式回應。公開研究方向：'+json.dumps(FOCUS,ensure_ascii=False)+'。未查證新聞標題候選：'+json.dumps(candidates,ensure_ascii=False),
        'max_output_tokens':6000,
        'text':{'format':{'type':'json_object'}}
    }
    req = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(req,timeout=150) as res:
            raw=json.load(res)
    except urllib.error.HTTPError as e:
        print('Beli brief: API request failed HTTP',e.code, e.read().decode('utf-8','replace')[:300])
        raise SystemExit(1)
    if raw.get('status')=='incomplete':
        raise RuntimeError('Beli brief response incomplete: '+str(raw.get('incomplete_details')))
    texts=[part.get('text','') for item in raw.get('output',[]) for part in item.get('content',[]) if part.get('type')=='output_text']
    if not texts:
        raise RuntimeError('Beli brief: API output contains no text')
    document=json.loads(''.join(texts))
    source_by_id={r['id']:r for r in candidates}
    priorities=[]
    seen=set()
    for p in document.get('priorities',[]) if isinstance(document.get('priorities'),list) else []:
        if not isinstance(p,dict): continue
        sources=source_links(p.get('source_ids',[]),source_by_id)
        if not sources: continue
        signature=tuple(sorted(s['id'] for s in sources))
        if signature in seen: continue
        seen.add(signature)
        priorities.append({
            'headline':clean(p.get('headline'),70),'company':clean(p.get('company'),100),
            'priority':clean(p.get('priority'),12),'impact_type':clean(p.get('impact_type'),30),
            'evidence_summary':clean(p.get('evidence_summary'),320),
            'beli_implication':clean(p.get('beli_implication'),360),
            'next_check':clean(p.get('next_check'),260),
            'evidence_level':'僅 RSS 標題線索，未查證新聞全文',
            'sources':sources
        })
        if len(priorities)==5: break
    if not priorities: raise ValueError('Beli brief: no source-linked priority item; refusing publication')
    actions=[]
    for a in document.get('actions',[]) if isinstance(document.get('actions'),list) else []:
        if isinstance(a,dict) and a.get('question'):
            actions.append({k:clean(a.get(k),230) for k in ('priority','owner_suggestion','question','why')})
        if len(actions)>=6:break
    risks=[]
    for r in document.get('risks',[]) if isinstance(document.get('risks'),list) else []:
        if isinstance(r,dict) and r.get('title'):
            risks.append({k:clean(r.get(k),250) for k in ('level','title','detail')})
        if len(risks)>=4:break
    result={
        'schema_version':1,'status':'ok','generated_at':dt.datetime.now(TZ).isoformat(timespec='seconds'),
        'model':model,'title':'倍利科技本週決策封面','focus':FOCUS,
        'basis':'最近30日公開 RSS 新聞標題（非全文）；僅引用本次候選新聞 ID',
        'priorities':priorities,'actions':actions,'risks':risks,
        'disclaimer':'此封面僅根據公開 RSS 新聞標題進行初步推論；未交叉核對全文、企業官方公告、機型規格或客戶資訊。所列商機、產品應用、建議確認方向與風險均為假設，不代表倍利已具備相關能力、已有客戶採購需求或取得訂單。禁止放入任何未公開的 Intel／客戶或公司內部保密資料。'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('V5 decision brief generated:',len(priorities),'validated source-linked signals')

if __name__=='__main__': main()
