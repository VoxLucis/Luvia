#!/usr/bin/env python3
"""Optional weekly AI interpretation of RSS headline candidates; never claim verified article facts."""
import datetime as dt, json, os, pathlib, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
key=os.environ.get('OPENAI_API_KEY','').strip()
if not key:
    print('OPENAI_API_KEY not set; skipping optional AI analysis.')
    raise SystemExit(0)
news=json.loads((ROOT/'data/news.json').read_text(encoding='utf-8'))
items=news.get('items',[])
cutoff=dt.date.today()-dt.timedelta(days=21)
chosen=[]
for a in items:
    try:
        if dt.date.fromisoformat(a['date'])<cutoff: continue
    except Exception: continue
    title=a.get('title','')
    if not title or len(title)<18: continue
    chosen.append({'id':a['id'],'date':a.get('date'),'category':a.get('category'),'company':a.get('company'),'title':title,'url':a.get('url')})
    if len(chosen)>=24:break
if not chosen:
    print('No recent news candidates; skipping AI analysis.')
    raise SystemExit(0)
model=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
instructions="""你是謹慎的半導體產業情報編輯。輸入只有新聞標題及中繼資料，沒有文章全文！不得編造投資金額、廠址、時程、已確認訂單或來源。以繁體中文輸出合法 JSON 物件，不要 Markdown，格式：{"week_summary":"兩到四句總覽，聲明僅為標題推論","disclaimer":"僅根據RSS標題初步整理，未核對全文和官方公告，設備需求為假設","signals":[{"id":"輸入的id","headline":"20字內事件標題","company":"企業名稱","priority":"高/中/低","evidence_level":"僅新聞標題，未驗證","summary":"最多80字，明確指出是標題顯示、不能確證","equipment_implication":"最多90字，講可能關注的檢測設備類別，無關就寫尚無直接訊號"}]}。只選最相關的最多8則，不要重複。只引用清單中真實存在的id。拒絕把新聞候選視為官方證據。"""
payload={'model':model,'instructions':instructions,'input':'候選新聞（未核實）：'+json.dumps(chosen,ensure_ascii=False),'max_output_tokens':6500,'text':{'format':{'type':'json_object'}}}
req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
try:
    with urllib.request.urlopen(req,timeout=120) as res: raw=json.load(res)
except urllib.error.HTTPError as exc:
    print('OpenAI API error',exc.code,exc.read().decode('utf-8','replace')[:400]);raise SystemExit(1)
parts=[]
for item in raw.get('output',[]):
    for c in item.get('content',[]):
        if c.get('type')=='output_text': parts.append(c.get('text',''))
if raw.get('status') == 'incomplete':
    reason = (raw.get('incomplete_details') or {}).get('reason', 'unknown')
    raise RuntimeError(f'AI response incomplete ({reason}); JSON may be truncated')
text=''.join(parts).strip()
if not text:
    raise RuntimeError('AI returned no text; check the Responses API output and model availability')
if text.startswith('```'):
    text=text.split('\n',1)[-1].rsplit('```',1)[0].strip()
try:
    doc=json.loads(text)
except json.JSONDecodeError as exc:
    raise RuntimeError(f'AI returned malformed JSON at character {exc.pos}. No report was published.') from exc
ids={a['id']:a for a in chosen}
validated=[]
for s in doc.get('signals',[])[:8]:
    if not isinstance(s,dict) or s.get('id') not in ids:continue
    original=ids[s['id']]
    validated.append({k:str(s.get(k,''))[:500] for k in ['headline','company','priority','evidence_level','summary','equipment_implication']}|{'source_url':original['url'],'source_title':original['title'],'source_date':original['date'],'id':s['id']})
if not validated: raise ValueError('AI output has no valid source-linked signals')
result={'generated_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),'model':model,'week_summary':str(doc.get('week_summary',''))[:1500],'disclaimer':'僅根據 RSS 標題推論，未核對全文和官方公告；設備需求不是已確認訂單。','signals':validated}
(ROOT/'data/ai_brief.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AI brief generated:',len(validated),'source-linked signals')
