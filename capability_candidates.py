#!/usr/bin/env python3
"""Produce REVIEW-ONLY official technology candidates using captured quotations.

AI is optional. Its proposals must match exact scanner excerpts and can never
write verified equipment capabilities. A separate human approval is required.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,urllib.request,urllib.error

DATA=Path(__file__).resolve().parent/'data'
def load(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def stable_id(company,tech,url,excerpt):
    return 'cap-'+hashlib.sha256((company+'\x1f'+tech+'\x1f'+url+'\x1f'+excerpt).encode()).hexdigest()[:16]

def ask_ai(candidates):
    """Optional bounded summary; returned text is never treated as evidence."""
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key or not candidates:return {}
    model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini')
    instructions=('你是半導體設備官網資料審核助手。僅依提供的原文片段生成 json 物件；不可以補充未出現的機型、規格、性能、功能、客戶或訂單。'
                  '輸出格式 {"items":[{"id":"輸入id","summary":"中文50字內的暫定解讀","product":"原文確實出現的產品名稱，否則空字串"}]}。'
                  '所有內容都是待人工核對線索，絕不自稱已經查證。')
    payload={'model':model,'instructions':instructions,'input':'請輸出 json 物件。以下是官方頁面截取的候選原文：'+json.dumps(candidates,ensure_ascii=False),
             'max_output_tokens':2500,'text':{'format':{'type':'json_object'}}}
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=35) as resp: response=json.loads(resp.read())
        if response.get('status')=='incomplete':raise ValueError('incomplete response')
        text=''.join(c.get('text','') for output in response.get('output',[]) for c in output.get('content',[]) if c.get('type')=='output_text')
        result=json.loads(text)
        valid_ids={item['id'] for item in candidates}
        return {x['id']:x for x in result.get('items',[]) if isinstance(x,dict) and x.get('id') in valid_ids}
    except (ValueError,KeyError,urllib.error.URLError,TimeoutError) as exc:
        print('Optional AI candidate annotation unavailable:',type(exc).__name__,str(exc)[:150]);return {}

def main():
    scan=load(DATA/'official_matrix_leads.json',{})
    matrix=load(DATA/'equipment_matrix.json',{})
    previous=load(DATA/'capability_candidates.json',{})
    existing={x['id']:x for x in previous.get('candidates',[]) if 'id' in x}
    confirmed={(c['name'],t) for c in matrix.get('companies',[]) for t,e in c.get('evidence',{}).items() if e.get('status')=='verified'}
    present=[]; seen=set()
    for page in scan.get('pages',[]):
        if page.get('status')!='fetched':continue
        company=page.get('company','');url=page.get('url','')
        for tech,match in page.get('matches',{}).items():
            if (company,tech) in confirmed:continue
            excerpts=match.get('excerpts') or [match.get('excerpt','')]
            for excerpt in excerpts[:2]:
                if len(excerpt)<20:continue
                cid=stable_id(company,tech,url,excerpt)
                if cid in seen:continue
                seen.add(cid)
                older=existing.get(cid,{})
                present.append({'id':cid,'company':company,'technology':tech,'url':url,'excerpt':excerpt,'source_page_title':page.get('page_title',''),
                    'source_checked_at':page.get('checked_at'),'first_seen':older.get('first_seen') or datetime.now(timezone.utc).isoformat(),
                    'status':older.get('status','pending'), 'summary':older.get('summary',''), 'product':older.get('product',''),
                    **{k:older[k] for k in ('reviewed_at','reviewer','review_note') if k in older}})
    # Preserve previously reviewed outcomes, and pending candidates even when a site is temporarily inaccessible.
    current_ids={x['id'] for x in present}
    for older in existing.values():
        if older['id'] not in current_ids:
            item=older.copy();item['not_seen_in_latest_scan']=True;present.append(item)
    pending=[{'id':x['id'],'company':x['company'],'technology':x['technology'],'excerpt':x['excerpt']} for x in present if x['status']=='pending' and not x.get('summary')][:20]
    annotations=ask_ai(pending)
    for x in present:
        a=annotations.get(x['id'],{})
        if a:
            # AI label is explicitly non-evidentiary; no status changes.
            x['summary']=str(a.get('summary',''))[:160]
            candidate_product=str(a.get('product','')).strip()[:120]
            x['product']=candidate_product if candidate_product and candidate_product.casefold() in x['excerpt'].casefold() else ''
    present=sorted(present,key=lambda x:(x['status']!='pending',x['company'],x['technology'],x['id']))[:350]
    out={'schema_version':1,'updated_at':datetime.now(timezone.utc).isoformat(),'scan_status':f'官方擷取 {sum(p.get("status")=="fetched" for p in scan.get("pages",[]))}/{len(scan.get("pages",[]))} 頁',
        'method':'官網原文候選；AI 只補暫定摘要。核准須人工閱讀官方原文，核准前不得更新正式能力。','candidates':present}
    DATA.mkdir(exist_ok=True)
    (DATA/'capability_candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Capability candidates:',len(present),'pending:',sum(c['status']=='pending' for c in present))
if __name__=='__main__':main()
