#!/usr/bin/env python3
"""Read RSS headline candidates already in data/news.json and produce unverified technology leads.

No AI API needed here; existing AI brief remains separate. Never changes verified capability matrix.
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
NOW=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
STOCK=re.compile(r'\b(stock|stocks|share price|shares|target price|price target|analyst rating|technical analysis|tradingview|nasdaq|earnings per share|eps|stock forecast|stock prediction|market cap|buy or sell|investment comparison)\b|股價|股票|目標價|技術分析|法人評等|券商評等',re.I)
KEYWORDS={
 'aoi':re.compile(r'\baoi\b|automated optical inspection|optical inspection|machine vision|自動光學檢測|光學檢測|視覺檢測',re.I),
 '3d':re.compile(r'3d (?:inspection|metrology|measurement)|3d optical|three.dimension|立體量測|三維檢測|3D量測',re.I),
 'adc':re.compile(r'\badc\b|automatic defect classification|automated defect classification|defect classification|AI defect (?:screening|detection|inspection)|缺陷分類|AI 缺陷|AI瑕疵|AI檢測',re.I),
 'xray':re.compile(r'\bx.?ray\b|computed tomography|\bct inspection\b|X光檢測|電腦斷層',re.I),
 'csam':re.compile(r'\bcsam\b|scanning acoustic|acoustic microscopy|超音波掃描|聲學顯微',re.I),
 'packaging':re.compile(r'cowos|soic|hbm|advanced packaging|heterogeneous integration|hybrid bonding|先進封裝|異質整合|混合鍵合',re.I),
 'tray':re.compile(r'jedec tray|tray inspection|six.side|six.face|六面檢測|托盤檢測|載盤檢測',re.I)
}
TECH_CONTEXT=re.compile(r'inspection|defect|metrology|measurement|equipment|tool|technology|automation|manufacturing|launch|product|solution|檢測|量測|設備|技術|產品|缺陷|瑕疵|製程|封裝|影像|自動化|量產',re.I)

def main():
 registry=json.loads((DATA/'companies.json').read_text(encoding='utf-8'))
 allowed=[c for c in registry.get('companies',[]) if c.get('enabled',True) and c.get('group')=='competitor']
 news=json.loads((DATA/'news.json').read_text(encoding='utf-8'))
 old_path=DATA/'equipment_signals.json'
 old=json.loads(old_path.read_text(encoding='utf-8')) if old_path.exists() else {'signals':[]}
 existing={x.get('id'):x for x in old.get('signals',[]) if isinstance(x,dict) and x.get('id')}
 additions=0; filtered=0
 for item in news.get('items',[]):
  title=str(item.get('title',''))
  if not title or not TECH_CONTEXT.search(title) or STOCK.search(title):
   filtered+=1;continue
  matches=[k for k,rx in KEYWORDS.items() if rx.search(title)]
  if not matches:filtered+=1;continue
  low=title.casefold()
  firms=[]
  for c in allowed:
   aliases=[c['name']]+c.get('aliases',[])
   if any(len(a.strip())>=3 and a.strip().casefold() in low for a in aliases):firms.append(c['name'])
  # No name match => no attribution. A company field alone may be a broad category placeholder.
  if not firms:filtered+=1;continue
  for firm in firms:
   key=hashlib.sha256((firm+'|'+title.casefold()).encode()).hexdigest()[:16]
   if key in existing:continue
   existing[key]={'id':key,'company':firm,'title':title[:350],'date':str(item.get('date','')),
                  'url':str(item.get('url','')),'source':str(item.get('source','')),
                  'technologies':matches,'priority':'高' if len(matches)>1 else '中',
                  'evidence_level':'僅RSS標題；未核實技術能力'}
   additions+=1
 records=sorted(existing.values(),key=lambda d:(d.get('date',''),d.get('id','')),reverse=True)[:150]
 doc={'updated_at':NOW.isoformat(),'scan_status':f'檢查 {len(news.get("items",[]))} 則候選；排除不相關／財經雜訊 {filtered} 則；新增 {additions} 筆技術線索',
      'method':'關鍵字候選分類，不是官方規格確認；AI週報獨立生成。','signals':records}
 old_path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(doc['scan_status'])

if __name__=='__main__':main()
