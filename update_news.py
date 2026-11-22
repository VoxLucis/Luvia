#!/usr/bin/env python3
"""Weekly public headline candidates: registry-aware RSS, no invented source verification."""
import datetime as dt
import email.utils
import hashlib
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

ROOT=pathlib.Path(__file__).resolve().parent
DATA=ROOT/'data'
DATA.mkdir(exist_ok=True)
BASE_QUERIES={
 '擴廠動態':['TSMC ASE semiconductor fab expansion tool move','Intel Samsung Micron SK hynix fab expansion'],
 '政治與政策':['US BIS export controls semiconductor equipment China','CHIPS Act semiconductor Taiwan US policy'],
 '檢測設備':['KLA Camtek Onto semiconductor inspection metrology','automated defect classification semiconductor AI AOI CSAM'],
 'AI 與技術':['semiconductor manufacturing AI defect detection'],
 '先進封裝':['CoWoS SoIC HBM hybrid bonding advanced packaging'],
 '供應鏈與資本支出':['SEMI semiconductor equipment capital expenditure forecast']
}
NOISE=re.compile(r'\b(stock price|share price|stock quote|stock prediction|price target|market forecast|air showers|market cap|stock analysis|stock titan)\b',re.I)
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
registry=json.loads((DATA/'companies.json').read_text(encoding='utf-8'))
companies=[c for c in registry.get('companies',[]) if c.get('enabled',True)]
REGIONS={'Arizona':'美國','Texas':'美國','United States':'美國','Taiwan':'台灣','Kaohsiung':'台灣','Japan':'日本','Kumamoto':'日本','Germany':'德國','Dresden':'德國','China':'中國','Korea':'韓國'}

def company_match(title,company):
    for alias in company.get('aliases',[]):
        alias=alias.strip()
        if not alias:continue
        if re.search(r'[\u4e00-\u9fff]',alias):
            if alias.lower() in title.lower():return True
        elif re.search(r'(?<![\w])'+re.escape(alias)+r'(?![\w])',title,re.I):return True
    return False

def canonical(title):
    matches=[c for c in companies if company_match(title,c)]
    return max(matches,key=lambda c:max((len(x) for x in c.get('aliases',[])),default=0))['name'] if matches else '多家公司'

p=DATA/'news.json'
old=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'items':[]}
items={i['id']:i for i in old.get('items',[]) if isinstance(i,dict) and 'id' in i}
added=0
failures=[]
feeds=[(cat,q,None) for cat,queries in BASE_QUERIES.items() for q in queries]
for c in companies:
    query=(c.get('search_query') or c['name']+' semiconductor inspection').strip()
    feeds.append(('檢測設備' if c['group']=='competitor' else '擴廠動態',query,c))
for category,query,tracked in feeds:
    params=urllib.parse.urlencode({'q':query+' when:14d','hl':'en-US' if not re.search(r'[\u4e00-\u9fff]',query) else 'zh-TW','gl':'US' if not re.search(r'[\u4e00-\u9fff]',query) else 'TW','ceid':'US:en' if not re.search(r'[\u4e00-\u9fff]',query) else 'TW:zh-Hant'})
    url='https://news.google.com/rss/search?'+params
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 SemiconIntelligence/3.0'})
        with urllib.request.urlopen(req,timeout=20) as f: feed=ET.fromstring(f.read())
        for node in feed.findall('./channel/item')[:10]:
            title=unescape(re.sub('<[^>]+>','',node.findtext('title','')).strip())
            link=node.findtext('link','').strip()
            if not title or not link or NOISE.search(title):continue
            try: day=email.utils.parsedate_to_datetime(node.findtext('pubDate','')).date().isoformat()
            except Exception:continue
            if (now.date()-dt.date.fromisoformat(day)).days>21:continue
            # A company-specific search is not evidence the article actually refers to that company.
            if tracked and not company_match(title,tracked):continue
            key=hashlib.sha256(title.casefold().encode('utf-8')).hexdigest()[:18]
            if key in items:continue
            found=canonical(title)
            region=next((v for k,v in REGIONS.items() if k.lower() in title.lower()),'全球')
            src=node.find('source')
            source=src.text.strip() if src is not None and src.text else 'Google News RSS'
            items[key]={'id':key,'title':title,'summary':'自動蒐集的新聞標題；尚未核對全文及原始公告。','category':category,'company':found,'region':region,'date':day,'source':source,'url':link,'status':'自動蒐集・未查核','impact':'待研判；不代表已確認的擴廠、採購或設備訂單。','tags':[found] if found!='多家公司' else [],'collected_at':now.isoformat()}
            added+=1
    except Exception as exc:failures.append(f'{category} {query[:45]}: {type(exc).__name__}: {exc}')
cutoff=(now.date()-dt.timedelta(days=90)).isoformat()
clean=[v for v in items.values() if (v.get('status')!='自動蒐集・未查核' or v.get('date','')>=cutoff) and (v.get('status')!='自動蒐集・未查核' or not NOISE.search(v.get('title','')))]
clean.sort(key=lambda a:(a.get('date',''),a.get('id','')),reverse=True)
if added==0 and len(failures)==len(feeds):
    print('All feeds failed; preserving prior dataset.')
    for error in failures:print(error)
    raise SystemExit(1)
latest={'updated_at':now.isoformat(),'mode':'automated-candidates','items':clean[:450]}
p.write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive_p=DATA/'archive.json'
archive=json.loads(archive_p.read_text(encoding='utf-8')) if archive_p.exists() else []
filename=f"archive/{now.date().isoformat()}.json"
(DATA/'archive').mkdir(exist_ok=True)
(DATA/filename).write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive=[x for x in archive if x.get('date')!=now.date().isoformat()]+[{'date':now.date().isoformat(),'file':'data/'+filename,'count':len(latest['items'])}]
archive_p.write_text(json.dumps(sorted(archive,key=lambda x:x['date']),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Tracked companies:',len(companies),'New candidates:',added,'Stored:',len(latest['items']),'Failed feeds:',len(failures),'of',len(feeds))
for failure in failures:print(failure)
