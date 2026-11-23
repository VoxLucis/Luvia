#!/usr/bin/env python3
"""Fetch allowlisted public, official pages. Matches remain unverified leads."""
from html.parser import HTMLParser
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import urllib.request

DATA = Path(__file__).resolve().parent / 'data'
# Source URLs seeded from the V6.1 reviewed evidence registry; they are not
# a guarantee of website accessibility. Do not follow arbitrary user URL input.
SOURCES = {
    'KLA': ['https://ir.kla.com/news-events/press-releases/detail/9/kla-announces-enhanced-portfolio-of-systems-for-advanced'],
    'Camtek': ['https://www.camtek.com/markets/advanced-packaging/', 'https://www.camtek.com/products/eaglet-ap/'],
    'Onto Innovation': ['https://ontoinnovation.com/products/dragonfly-g3/'],
    '由田': ['https://www.utechzone.com.tw/'],
    '牧德': ['https://www.machvision.com.tw/'],
    'SixSense': ['https://www.sixsense.ai/product/'],
}
PATTERNS = {
    'aoi': r'\bAOI\b|automated optical inspection|optical inspection|2D inspection|自動光學檢測|光學檢測',
    '3d': r'\b3D\b|three.dimension|三維|3D量測|3D metrology',
    'adc': r'\bADC\b|defect classification|classification of defects|缺陷分類|AI defect',
    'xray': r'x.ray|computed tomography|\bCT inspection\b',
    'csam': r'\bCSAM\b|scanning acoustic|acoustic microscopy',
    'packaging': r'advanced packaging|heterogeneous integration|\bHBM\b|先進封裝|IC載板|wafer.level packaging',
    'tray': r'JEDEC tray|six.side|six.face|六面檢測|tray inspection',
}
class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[];self.skips=[];self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','svg','nav','footer'):self.skips.append(tag)
        if tag=='title': self.in_title=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if tag in self.skips:self.skips.remove(tag)
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if not self.skips:self.parts.append(data)

def collect(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; SemiconIntelligenceResearch/1.2; public-pages-only)'})
    with urllib.request.urlopen(req,timeout=15) as response:
        if 'text/html' not in response.headers.get('Content-Type','').lower():raise ValueError('Not HTML')
        raw=response.read(650000);charset=response.headers.get_content_charset() or 'utf-8'
        parser=VisibleText();parser.feed(raw.decode(charset,errors='replace'))
        text=re.sub(r'\s+',' ',' '.join(parser.parts)).strip()[:50000]
        return text,re.sub(r'\s+',' ',' '.join(parser.title)).strip()[:200]

def excerpt_windows(text,pattern):
    results=[];seen=set()
    for m in list(re.finditer(pattern,text,re.I))[:8]:
        a=max(0,m.start()-145);b=min(len(text),m.end()+225)
        quote=text[a:b].strip()[:400]
        if quote not in seen:results.append(quote);seen.add(quote)
        if len(results)==3:break
    return results

def main():
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    path=DATA/'official_matrix_leads.json'
    try:old=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):old={}
    previous={(x.get('company'),x.get('url')):x for x in old.get('pages',[])}
    pages=[]
    for company,urls in SOURCES.items():
        for url in urls:
            earlier=previous.get((company,url),{})
            entry={'company':company,'url':url,'checked_at':now,'status':'unavailable','matches':{},'changed_since_last_scan':None}
            try:
                text,title=collect(url)
                if len(text)<30:raise ValueError('Page has insufficient visible text')
                fingerprint=hashlib.sha256(text.encode()).hexdigest()
                entry.update(status='fetched',page_title=title,page_text_hash=fingerprint,
                             changed_since_last_scan=(fingerprint!=earlier.get('page_text_hash')) if earlier.get('page_text_hash') else None)
                for tech,pattern in PATTERNS.items():
                    excerpts=excerpt_windows(text,pattern)
                    if excerpts:
                        entry['matches'][tech]={'evidence_level':'官網原文片段（未審核）','excerpt':excerpts[0], 'excerpts':excerpts}
            except Exception as exc:
                entry['error']=type(exc).__name__+': '+str(exc)[:160]
                if earlier.get('status')=='fetched':entry['last_successful_result']=earlier.get('matches',{})
            pages.append(entry)
    out={'schema_version':2,'updated_at':now,'method':'官方公開頁面文字擷取；片段為自動候選，絕不直接寫入已核實能力。網站不可讀取時保留既有人工核實證據。','pages':pages}
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Official pages:',len(pages),'fetched:',sum(p['status']=='fetched' for p in pages))
if __name__=='__main__': main()
