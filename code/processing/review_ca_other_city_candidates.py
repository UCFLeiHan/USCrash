"""Final conservative review before coordinate-only promotion."""
import json,shutil
from pathlib import Path
import pandas as pd
from pilot_ca_composite_coordinates import U
from coordinate_supplement_utils import sha
P=U/'qa/CA_other_cities_2026-10-16';plan=json.loads((P/'proposal_manifest.json').read_text());backup=P/'proposals_before_placeholder_review';backup.mkdir(exist_ok=True)
invalid={'NULL','NONE','UNKNOWN','UNNAMED','UNNAMED RD','UNKNOWN RD','NOT STATED','N A','NAN','0','PARKING LOT','UNSPECIFIED','NOT APPLICABLE'};rows=[]
for item in plan['annual']:
 y=item['year'];f=P/f'CA_{y}_proposed.csv'
 if not item['proposed']:rows.append({'year':y,'proposed_before':0,'held_placeholder_road':0,'accepted':0});continue
 if not (backup/f.name).exists():shutil.copy2(f,backup/f.name)
 d=pd.read_csv(backup/f.name,dtype=str,keep_default_na=False)
 bad=d.roads.map(lambda s:any(x.strip() in invalid or not x.strip() for x in s.split('|')) or len(s.split('|'))!=2)
 d.loc[bad].to_csv(P/f'CA_{y}_held_placeholder_roads.csv',index=False);d=d.loc[~bad].copy();assert d.crash_uid.is_unique
 d.to_csv(f,index=False);rows.append({'year':y,'proposed_before':item['proposed'],'held_placeholder_road':int(bad.sum()),'accepted':len(d),'accepted_file_sha256':sha(f)});item['proposed']=len(d)
plan['total_proposed']=sum(x['accepted'] for x in rows);plan['placeholder_review']='Generic/unknown road labels excluded; initial proposals preserved.';(P/'proposal_manifest.json').write_text(json.dumps(plan,indent=2));pd.DataFrame(rows).to_csv(P/'final_candidate_review.csv',index=False)
print('ACCEPTED',plan['total_proposed'],'HELD',sum(x['held_placeholder_road'] for x in rows),flush=True)
