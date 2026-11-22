#!/usr/bin/env python3
"""Weekly Google News RSS headline collector. Unverified articles are labeled candidly."""
import datetime as dt, email.utils, hashlib, json, pathlib, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from html import unescape
ROOT=pathlib.Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
QUERIES={
 '擴廠動態': ['TSMC fab expansion tool move in Arizona Japan Germany','ASE semiconductor advanced packaging expansion Kaohsiung','Intel Samsung Micron SK hynix semiconductor fab construction'],
 '政治與政策':['US BIS export controls semiconductor equipment China','CHIPS Act tariff semiconductor Taiwan US policy'],
 '檢測設備':['KLA Camtek Onto Innovation semiconductor inspection metrology','automated defect classification semiconductor inspection AI AOI CSAM'],
 'AI 與技術':['semiconductor manufacturing AI defect detection model 2026','AI chip manufacturing yield semiconductor'],
 '先進封裝':['CoWoS SoIC HBM hybrid bonding advanced packaging expansion'],
 '供應鏈與資本支出':['semiconductor capital expenditure equipment orders fab 2026','SEMI equipment spending wafer fab forecast 2026']
}
COMPANIES={'TSMC':'台積電','台積電':'台積電','ASE':'日月光','日月光':'日月光','Intel':'Intel','Samsung':'Samsung','SK hynix':'SK hynix','Micron':'Micron','KLA':'KLA','Camtek':'Camtek','Onto':'Onto Innovation','ASML':'ASML','Lam Research':'Lam Research','Applied Materials':'Applied Materials','UMC':'UMC','GlobalFoundries':'GlobalFoundries','SMIC':'SMIC'}
REGIONS={'Arizona':'美國','Texas':'美國','United States':'美國','Taiwan':'台灣','Kaohsiung':'台灣','Japan':'日本','Kumamoto':'日本','Germany':'德國','Dresden':'德國','China':'中國','Korea':'韓國'}
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
p=DATA/'news.json'; old=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'items':[]}
items={it['id']:it for it in old.get('items',[])};added=0; failures=[]
for category,queries in QUERIES.items():
 for query in queries:
  params=urllib.parse.urlencode({'q':query+' when:14d','hl':'en-US','gl':'US','ceid':'US:en'})
  url='https://news.google.com/rss/search?'+params
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 SemiconIntelligence/1.0'})
   with urllib.request.urlopen(req,timeout=18) as f: root=ET.fromstring(f.read())
   for node in root.findall('./channel/item')[:12]:
    title=unescape(re.sub('<[^>]+>','',node.findtext('title','')).strip());link=node.findtext('link','').strip();date=node.findtext('pubDate','')
    if not title or not link:continue
    try:day=email.utils.parsedate_to_datetime(date).date().isoformat()
    except Exception:continue
    if (now.date()-dt.date.fromisoformat(day)).days>21:continue
    key=hashlib.sha256((title.lower()).encode()).hexdigest()[:18]
    if key in items:continue
    company=next((v for k,v in COMPANIES.items() if k.lower() in title.lower()),'多家公司')
    region=next((v for k,v in REGIONS.items() if k.lower() in title.lower()),'全球')
    source=node.find('source');source_name=source.text.strip() if source is not None and source.text else 'Google News RSS'
    items[key]={'id':key,'title':title,'summary':'自動蒐集的新聞標題；尚未核對全文及原始公告。請點擊原文確認報導內容。','category':category,'company':company,'region':region,'date':day,'source':source_name,'url':link,'status':'自動蒐集・未查核','impact':'待人工研判；勿將此候選消息視為已證實之設備需求。','tags':[query.split(' ')[0]],'collected_at':now.isoformat()};added+=1
  except Exception as e: failures.append(f'{category}: {type(e).__name__}: {e}')
# preserve manually verified seed indefinitely, retain last 90d of automated candidate items
cutoff=(now.date()-dt.timedelta(days=90)).isoformat()
clean=[v for v in items.values() if v.get('status')!='自動蒐集・未查核' or v.get('date','')>=cutoff]
clean.sort(key=lambda a:(a.get('date',''),a.get('id','')),reverse=True)
if added==0 and failures: print('All feeds failed; preserving prior dataset.'); print('\n'.join(failures)); raise SystemExit(1)
latest={'updated_at':now.isoformat(),'mode':'automated-candidates','items':clean[:450]}
p.write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive_p=DATA/'archive.json'; archive=json.loads(archive_p.read_text(encoding='utf-8')) if archive_p.exists() else []
week=now.date().isoformat();filename=f'archive/{week}.json';(DATA/'archive').mkdir(exist_ok=True)
(DATA/filename).write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive=[x for x in archive if x.get('date')!=week]+[{'date':week,'file':'data/'+filename,'count':len(clean)}]
archive_p.write_text(json.dumps(sorted(archive,key=lambda x:x['date']),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Added',added,'Total',len(clean),'Feed failures',len(failures))
for f in failures: print(f)
