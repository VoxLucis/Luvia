#!/usr/bin/env python3
"""Conservative cross-week headline tracking, without inventing confirmed milestones.

Uses saved weekly snapshots only; identical syndicated titles don't count as changes.
"""
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

DATA=Path(__file__).resolve().parent/'data'
TOPICS={
 '擴廠／建廠':r'fab|plant|factory|expansion|expand|facility|construction|groundbreak|擴廠|建廠|新廠|廠房',
 '設備／檢測':r'inspection|metrology|equipment|tool|aoi|adc|defect|檢測|量測|設備|瑕疵',
 '先進封裝／HBM':r'cowos|soic|packaging|hbm|hybrid bonding|封裝|混合鍵合',
 '投資／資本支出':r'capital spending|capex|investment|invest|資本支出|投資',
 '政策／管制':r'export control|sanction|tariff|chips act|restriction|出口管制|關稅|制裁',
 'AI／製程':r'artificial intelligence|machine learning|\bai\b|人工智慧|機器學習',
}
NOISE=re.compile(r'\bstock\b|share price|price target|analyst rating|股票|股價',re.I)
REGIONS={'arizona':'亞利桑那','kumamoto':'熊本','dresden':'德勒斯登','ohio':'俄亥俄','kaohsiung':'高雄','texas':'德州','new york':'紐約','malaysia':'馬來西亞'}

def main():
 archives=json.loads((DATA/'archive.json').read_text(encoding='utf-8'))
 weekly={}
 for entry in sorted(archives,key=lambda x:x.get('date','')):
  path=DATA.parent/entry.get('file','')
  if not path.is_file() or not path.resolve().is_relative_to(DATA.resolve()):continue
  try:weekly[entry['date']]=json.loads(path.read_text(encoding='utf-8')).get('items',[])
  except (ValueError,OSError):continue
 if not weekly:
  print('No weekly snapshots; preserving previous event file')
  return
 registry=json.loads((DATA/'companies.json').read_text(encoding='utf-8'))
 allowed={c['name'] for c in registry.get('companies',[]) if c.get('enabled',True)}
 events=defaultdict(lambda:{'weekly':defaultdict(list),'titles':set()})
 for week,items in weekly.items():
  for item in items:
   title=str(item.get('title','')).strip()
   firm=str(item.get('company','')).strip()
   if not title or firm not in allowed or NOISE.search(title):continue
   topics=[label for label,pattern in TOPICS.items() if re.search(pattern,title,re.I)]
   if not topics:continue
   loc=next((v for k,v in REGIONS.items() if k in title.lower()),'')
   # Conservative grouping: same named firm + topic + recognizable region.
   for topic in topics[:2]:
    key=(firm,topic,loc)
    title_key=re.sub(r'\W+',' ',title.casefold()).strip()
    if title_key in events[key]['titles']:continue
    events[key]['titles'].add(title_key)
    events[key]['weekly'][week].append({'title':title[:320],'date':item.get('date',''),'url':item.get('url',''),'source':item.get('source',''),'id':item.get('id','')})
 result=[]
 for (firm,topic,loc),evt in events.items():
  weeks=sorted(evt['weekly'])
  if not weeks:continue
  snapshots=[]
  for week in weeks:
   news=evt['weekly'][week]
   snapshots.append({'week':week,'new_headlines':len(news),'items':news[:8]})
  digest=hashlib.sha256(('|'.join((firm,topic,loc))).encode()).hexdigest()[:16]
  result.append({'id':digest,'company':firm,'topic':topic,'location':loc,'first_seen':weeks[0],
   'last_seen':weeks[-1],'weeks_seen':len(weeks),'headline_count':len(evt['titles']),
   'change_status':'有新標題待查證' if len(weeks)>1 else '首次觀察／基準',
   'change_summary':f'目前保存 {len(weeks)} 期不同的新聞標題。不同標題不代表廠區或技術真的有進展。',
   'timeline':snapshots[-12:],'evidence_level':'RSS 標題聚合，未核對全文；並非官方進度'})
 result.sort(key=lambda x:(x['last_seen'],x['weeks_seen'],x['headline_count']),reverse=True)
 out={'schema_version':1,'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
  'method':'依公司、主題、地點分組並比較每週新增標題；不推論已發生的廠區里程碑或採購。',
  'weeks_loaded':sorted(weekly),'events':result[:180]}
 (DATA/'event_history.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f"Event histories: {len(out['events'])}, snapshots: {len(weekly)}")

if __name__=='__main__':main()
