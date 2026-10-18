import json,sys
from collections import Counter
import pandas as pd
from replay_representative_years import W,R
for st in sys.argv[1:]:
 p=W/st/'report.json';r=json.loads(p.read_text(encoding='utf-8-sig'));y=r['year'];rel=f'Unified_MMUCC6/data/crash/{st}/{st}_crashes_harmonized_{y}.csv'
 a=pd.read_csv(R/rel,dtype=str,keep_default_na=False).set_index('crash_uid');b=pd.read_csv(W/st/rel,dtype=str,keep_default_na=False).set_index('crash_uid')
 common=a.index.intersection(b.index);a=a.loc[common];b=b.loc[common];counts={c:int(a[c].ne(b[c]).sum()) for c in a.columns if a[c].ne(b[c]).any()}
 d={'state':st,'column_differences':counts,'missing_ids':len(pd.read_csv(R/rel,usecols=['crash_uid']))-len(common),'extra_ids':len(pd.read_csv(W/st/rel,usecols=['crash_uid']))-len(common),'examples':{c:[{'id':i,'final':a.at[i,c],'replay':b.at[i,c]} for i in a.index[a[c].ne(b[c])][:3]] for c in counts}}
 (W/st/'differences.json').write_text(json.dumps(d,indent=2),encoding='utf8');print(json.dumps(d),flush=True)
