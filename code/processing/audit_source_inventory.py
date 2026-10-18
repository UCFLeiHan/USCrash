from __future__ import annotations
import csv,json,re,os
from pathlib import Path
ROOT=Path(r'F:\LH_Research\USCrash\Crash');STATES=ROOT/'States';PIPE=ROOT/'Unified_MMUCC6'
CODES='AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split()
URL=re.compile(r'https?://[^\s)>`]+')
# Resolve every source file actively used by formal configs.
active=set();configs={}
for cp in (PIPE/'config'/'states').glob('??.json'):
 cfg=json.loads(cp.read_text(encoding='utf-8'));s=cp.stem;configs[s]=cfg
 for v in cfg.get('versions',[]):
  for y in range(v['year_start'],v['year_end']+1):
   for pat in v['source_patterns']:
    p=STATES/s/str(y)/pat.format(year=y)
    if p.exists():active.add(p.resolve())

def read_small(p,limit=300000):
 try:
  if p.stat().st_size>limit:return ''
  return p.read_text(encoding='utf-8',errors='replace')
 except:return ''

def ability(cfg,key_options):
 if not cfg:return False
 return any(any(k in v.get('fields',{}) for k in key_options) for v in cfg.get('versions',[]))
inv=[];delete=[];review=[]
for s in CODES:
 sd=STATES/s; cfg=configs.get(s); source=sd/'SOURCE.md'; stxt=read_small(source) if source.exists() else ''
 years=sorted({y for v in cfg.get('versions',[]) for y in range(v['year_start'],v['year_end']+1)}) if cfg else []
 if not years and sd.exists():
  years=sorted(int(p.name) for p in sd.iterdir() if p.is_dir() and re.fullmatch(r'20\d{2}|19\d{2}',p.name))
 urls=sorted(set(URL.findall(stxt)))
 files=list(sd.rglob('*')) if sd.exists() else []
 real=[p for p in files if p.is_file()]
 exts={p.suffix.lower() or '[no_ext]' for p in real}
 tables=[]
 for ext,label in [('.csv','CSV'),('.xlsx','XLSX'),('.xls','XLS'),('.zip','ZIP'),('.json','JSON/GeoJSON'),('.gdb','FileGDB'),('.shp','Shapefile'),('.pdf','PDF/codebook')]:
  if ext in exts or any(ext in p.name.lower() for p in real):tables.append(label)
 # Add known multi-table level hints from names.
 names=' '.join(p.name.lower() for p in real)
 levels=[]
 for needle,label in [('crash','crash'),('accident','crash'),('vehicle','vehicle'),('unit','vehicle/unit'),('person','person/occupant'),('occupant','person/occupant'),('pedestrian','pedestrian')]:
  if needle in names and label not in levels:levels.append(label)
 docs=[]
 for p in real:
  low=p.name.lower()
  if (p==source or low in {'download_status.md','source.md'} or any(x in low for x in ('dictionary','codebook','guide','manual','metadata','request','license','disclaimer')) or 'code/acquisition' in [x.lower() for x in p.parts]):
   docs.append(str(p.relative_to(STATES)).replace('\\','/'))
 restriction=''
 corpus=stxt+'\n'+read_small(sd/'DOWNLOAD_STATUS.md') if sd.exists() else stxt
 meta_status=[]
 if sd.exists():
  for p in real:
   if ('status' in p.name.lower() or 'request' in p.name.lower() or 'license' in p.name.lower()) and p.suffix.lower() in {'.md','.txt'}:meta_status.append(read_small(p,100000))
 corpus+='\n'+'\n'.join(meta_status)
 cl=corpus.casefold()
 if 'paid/custom' in cl or 'request cost' in cl:restriction='PAID_CUSTOM_REQUEST_REQUIRED'
 elif 'application pending' in cl or ('submitted' in cl and 'request' in cl):restriction='APPLICATION_PENDING'
 elif 'request required' in cl or 'access required' in cl or 'public-records request' in cl:restriction='ACCESS_REQUEST_REQUIRED'
 elif 'restrict' in cl and ('copy' in cl or 'law' in cl):restriction='LEGAL_ACCESS_RESTRICTION'
 elif cfg:restriction='PUBLIC_OR_OFFICIALLY_PROVIDED_LOCAL_SOURCE; LICENSE_REVIEW_BEFORE_REDISTRIBUTION'
 else:restriction='NO_VERIFIED_HARMONIZABLE_LOCAL_SOURCE'
 status_override={'MD':'LOCAL_PARTIAL_NOT_FORMALLY_HARMONIZED','ND':'ACCESS_REQUEST_REQUIRED','NH':'ACCESS_REQUEST_REQUIRED','RI':'APPLICATION_DRAFT_UNCONFIRMED','SC':'PAID_CUSTOM_REQUEST_REQUIRED','WV':'APPLICATION_PENDING_NO_LOCAL_DATA'}
 if s in status_override:restriction=status_override[s]
 item={'state':s,'formal_config':bool(cfg),'official_agency':cfg.get('official_agency','') if cfg else '', 'coverage_years':years,'coverage_span':f'{min(years)}-{max(years)}' if years else '', 'source_md':source.exists(),'official_urls':urls,'table_formats':tables,'record_levels_inferred_from_filenames':levels,'field_capabilities':{'date_or_datetime':ability(cfg,['crash_date','crash_datetime','crash_year']) or (bool(years) and any(p.suffix.lower() in {'.csv','.xlsx','.xls'} for p in real)),'time':ability(cfg,['crash_datetime','crash_time_raw','crash_hour']) or bool(re.search(r'time\s*=\s*有',stxt,re.I)),'coordinates':ability(cfg,['latitude','longitude']) or bool(re.search(r'coords\s*=\s*有',stxt,re.I)),'severity':ability(cfg,['severity_raw_code','severity_raw_label','injury_severity_raw_code','severity_count_k','fatalities']) or bool(re.search(r'severity\s*=\s*有',stxt,re.I)),'manner':ability(cfg,['manner_raw_code','manner_raw_label']) or bool(re.search(r'manner\s*=\s*有',stxt,re.I)),'first_harmful_event':ability(cfg,['first_harmful_event_raw_code','first_harmful_event_raw_label'])},'access_or_license_status':restriction,'file_count':len(real),'documentation_and_scripts':sorted(set(docs))}
 inv.append(item)
 for p in real:
  rel=str(p.relative_to(STATES)).replace('\\','/');low=rel.casefold();resolved=p.resolve()
  if resolved in active:continue
  reason=None;confidence=None
  if any(part.casefold() in {'_probe','probe'} for part in p.parts):reason='PROBE_ARTIFACT';confidence='SAFE'
  elif p.name.casefold().endswith('.partial') or '.partial.' in p.name.casefold():reason='INCOMPLETE_PARTIAL';confidence='SAFE'
  elif p.suffix.casefold() in {'.tmp','.temp'} or p.name.startswith('~$'):reason='TEMPORARY_FILE';confidence='SAFE'
  elif any(x in p.name.casefold() for x in ('prepared','enriched')):
   # Derived files are safe only when a reproducible script/manifest exists locally.
   has_script=any(q.is_file() and q.suffix.lower()=='.py' for q in sd.rglob('*.py')) if sd.exists() else False
   has_manifest=any('manifest' in q.name.casefold() for q in real)
   if has_script and has_manifest:reason='UNREFERENCED_REGENERABLE_DERIVED';confidence='SAFE_AFTER_BACKUP'
   else:reason='UNREFERENCED_DERIVED_NEEDS_REVIEW';confidence='REVIEW_REQUIRED'
  elif any(x in p.name.casefold() for x in ('test','sample')) and p.suffix.lower() in {'.csv','.json','.xlsx','.zip'}:reason='TEST_OR_SAMPLE_NAMED_FILE';confidence='REVIEW_REQUIRED'
  if reason:
   rec={'state':s,'path':rel,'bytes':p.stat().st_size,'reason':reason,'confidence':confidence,'active_config_source':False}
   (delete if confidence == 'SAFE' else review).append(rec)
# Ensure protected categories never entered SAFE list.
protected_terms=('source.md','download_status','dictionary','codebook','guide','manual','request','license','disclaimer','code/acquisition/')
delete=[x for x in delete if not any(t in x['path'].casefold() for t in protected_terms)]
out=PIPE/'qa'/'source_inventory';out.mkdir(parents=True,exist_ok=True)
report={'draft':True,'states':inv,'safe_delete_candidates':delete,'review_required_candidates':review,'protection_policy':['Never delete active config sources','Retain unique originals','Retain codebooks/dictionaries/manuals','Retain request/access documentation','Retain download and preparation scripts'],'counts':{'jurisdictions':len(inv),'formal_configs':sum(x['formal_config'] for x in inv),'safe_delete_candidates':len(delete),'review_required_candidates':len(review),'safe_candidate_bytes':sum(x['bytes'] for x in delete)}}
(out/'source_inventory_draft.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with (out/'source_inventory_draft.csv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=['state','formal_config','official_agency','coverage_span','source_md','official_urls','table_formats','record_levels','date_or_datetime','time','coordinates','severity','manner','first_harmful_event','access_or_license_status','file_count']
 w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
 for x in inv:w.writerow({'state':x['state'],'formal_config':x['formal_config'],'official_agency':x['official_agency'],'coverage_span':x['coverage_span'],'source_md':x['source_md'],'official_urls':';'.join(x['official_urls']),'table_formats':';'.join(x['table_formats']),'record_levels':';'.join(x['record_levels_inferred_from_filenames']),**x['field_capabilities'],'access_or_license_status':x['access_or_license_status'],'file_count':x['file_count']})
for name,data in [('safe_delete_candidates.csv',delete),('review_required_cleanup_candidates.csv',review)]:
 with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
  fields=['state','path','bytes','reason','confidence','active_config_source'];w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data)
md=['# State Source Inventory Draft','','This is an audit-only inventory. No files were deleted.','','| State | Config | Coverage | Formats | Levels | Date/time | Coordinates | Severity | Manner | FHE | Access / license status |','|---|---:|---|---|---|---|---:|---:|---:|---:|---|']
for x in inv:
 cap=x['field_capabilities'];dt=('date' if cap['date_or_datetime'] else 'no date')+('/time' if cap['time'] else '')
 md.append(f"| {x['state']} | {'yes' if x['formal_config'] else 'no'} | {x['coverage_span'] or 'none'} | {', '.join(x['table_formats']) or 'none'} | {', '.join(x['record_levels_inferred_from_filenames']) or 'unknown'} | {dt} | {'yes' if cap['coordinates'] else 'no'} | {'yes' if cap['severity'] else 'no'} | {'yes' if cap['manner'] else 'no'} | {'yes' if cap['first_harmful_event'] else 'no'} | {x['access_or_license_status']} |")
md += ['', '## Cleanup assessment', '', f"- Safe direct-delete candidates: {len(delete)}", f"- Review-required or backup-first candidates: {len(review)}", '- Active config sources, unique originals, dictionaries, request records, and scripts were excluded from cleanup candidates.']
(out/'source_inventory_draft.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(json.dumps(report['counts'],indent=2));print('safe reasons', {r:sum(x['reason']==r for x in delete) for r in sorted(set(x['reason'] for x in delete))});print('review',len(review))
