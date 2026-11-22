#!/usr/bin/env python3
"""Apply owner-created GitHub issue to tracked-company registry; no credentials in browser."""
import json,os,re,pathlib,sys,datetime
root=pathlib.Path(__file__).resolve().parent
p=root/'data/companies.json'
body=os.environ.get('ISSUE_BODY','')
if len(body)>3000:sys.exit('Issue text exceeds limit')
fields={}
for line in body.splitlines():
    if ':' in line:
        k,v=line.split(':',1)
        if k.strip().upper() in {'ACTION','NAME','GROUP','ALIASES','SEARCH'}:
            fields[k.strip().upper()]=v.strip()
action=fields.get('ACTION','').lower()
name=fields.get('NAME','').strip()
if action not in ('add','remove') or not (2<=len(name)<=75) or any(ord(c)<32 for c in name):
    sys.exit('Invalid action/name')
name_re=re.compile(r'^[\w\-\s\u4e00-\u9fff.&+()]+$',re.U)
if not name_re.fullmatch(name):sys.exit('Name contains unsupported characters')
registry=json.loads(p.read_text(encoding='utf-8'))
companies=registry['companies']
index=next((i for i,c in enumerate(companies) if c['name'].casefold()==name.casefold()),None)
if action=='remove':
    if index is None:sys.exit('Company does not exist')
    companies.pop(index)
else:
    group=fields.get('GROUP','').lower()
    if group not in ('client','competitor'):sys.exit('Invalid group')
    if index is None and len(companies)>=45:sys.exit('Tracking list full')
    aliases=[a.strip() for a in fields.get('ALIASES','').split(',') if a.strip()]
    if not any(a.casefold()==name.casefold() for a in aliases): aliases.insert(0,name)
    if len(aliases)>6 or any(len(a)>75 or not name_re.fullmatch(a) for a in aliases):sys.exit('Invalid aliases')
    query=fields.get('SEARCH','')[:160].strip() or name+' semiconductor inspection'
    if any(ord(c)<32 for c in query):sys.exit('Invalid query')
    entry={'name':name,'group':group,'aliases':aliases,'search_query':query,'enabled':True}
    if index is None:companies.append(entry)
    else:companies[index]=entry
registry['updated_at']=datetime.date.today().isoformat()
p.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Registry change:',action,name)
