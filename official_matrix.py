#!/usr/bin/env python3
"""Gather limited text from an allowlist of official product pages.

Keyword matches are leads only, never verified capability claims.
"""
from html.parser import HTMLParser
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import ssl
import urllib.request

DATA=Path(__file__).resolve().parent/'data'
SOURCES={
 'Camtek':['https://www.camtek.com/solutions/inspection-metrology/'],
 'Onto Innovation':['https://ontoinnovation.com/product-categories/inspection/'],
 '由田':['https://www.utechzone.com.tw/'],
 '牧德':['https://www.machvision.com.tw/about/'],
 'SixSense':['https://www.sixsense.ai/product/'],
}
PATTERNS={
 'aoi':r'\bAOI\b|automated optical inspection|optical inspection|自動光學檢測|光學檢測',
 '3d':r'\b3D\b|three.dimension|三維|3D量測',
 'adc':r'\bADC\b|defect classification|classifai|缺陷分類',
 'xray':r'x.ray|computed tomography|\bCT inspection\b',
 'csam':r'\bCSAM\b|scanning acoustic|acoustic microscopy',
 'packaging':r'advanced packaging|heterogeneous integration|\bHBM\b|先進封裝|IC載板',
 'tray':r'JEDEC tray|six.side|six.face|六面檢測|tray inspection',
}
class VisibleText(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','noscript','svg'):self.skip+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript','svg') and self.skip:self.skip-=1
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)

def collect(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; SemiconIntelligenceResearch/1.0; public-pages-only)'})
 with urllib.request.urlopen(req,timeout=12) as resp:
  content_type=resp.headers.get('Content-Type','')
  if 'text/html' not in content_type.lower():raise ValueError('Not HTML')
  raw=resp.read(650000)
  charset=resp.headers.get_content_charset() or 'utf-8'
  parsed=VisibleText(); parsed.feed(raw.decode(charset,errors='replace'))
  return re.sub(r'\s+',' ',' '.join(parsed.parts)).strip()[:30000]

def main():
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 path=DATA/'official_matrix_leads.json'
 try: old=json.loads(path.read_text(encoding='utf-8'))
 except (OSError,ValueError):old={}
 previous={(x['company'],x['url']):x for x in old.get('pages',[]) if 'company' in x and 'url' in x}
 pages=[]
 for company,urls in SOURCES.items():
  for url in urls:
   old_entry=previous.get((company,url),{})
   entry={'company':company,'url':url,'checked_at':now,'status':'unavailable','matches':{},'changed_since_last_scan':None}
   try:
    text=collect(url)
    if not text:raise ValueError('Empty visible text')
    fingerprint=hashlib.sha256(text.encode()).hexdigest()
    entry['status']='fetched';entry['page_text_hash']=fingerprint
    entry['changed_since_last_scan']=fingerprint!=old_entry['page_text_hash'] if old_entry.get('page_text_hash') else None
    for tech,pattern in PATTERNS.items():
     m=re.search(pattern,text,re.I)
     if m:
      start=max(0,m.start()-100);end=min(len(text),m.end()+140)
      entry['matches'][tech]={'evidence_level':'官網文字命中（未核實機型與規格）','excerpt':text[start:end].strip()[:240]}
   except Exception as exc:
    entry['error']=type(exc).__name__ + ': '+str(exc)[:160]
    if old_entry.get('status')=='fetched':entry['last_successful_result']=old_entry.get('matches',{})
   pages.append(entry)
 out={'schema_version':1,'updated_at':now,'method':'僅搜尋官方公開網頁中的文字命中；不自動把命中記入 data/equipment_matrix.json 已證實能力。頁面可能阻擋擷取。','pages':pages}
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Official pages:',len(pages),'fetched:',sum(p['status']=='fetched' for p in pages))
if __name__=='__main__':main()
