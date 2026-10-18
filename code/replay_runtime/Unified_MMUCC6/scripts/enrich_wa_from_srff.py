"""Deterministic WA CAT + agency SRFF union, staged validation and promotion.

Original source files are immutable. The immutable baseline is archived before
the first promotion. Rerun from that baseline, or after a fresh CAT harmonization.
Every changed canonical cell has a before/after record in a compressed JSONL.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,shutil,os
from datetime import datetime,timezone
import pandas as pd
import numpy as np

ROOT=Path(os.environ.get('USCRASH_ROOT',r'F:\LH_Research\USCrash\Crash'))
P=ROOT/'Unified_MMUCC6';S=ROOT/'States/WA'; DATA=P/'data/crash/WA'
REV='WA_SRFF_2026-10-15_v1'
Q=P/'qa/revisions'/REV
BACK=Q/'baseline'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p,**kw):return pd.read_csv(p,dtype=str,keep_default_na=False,low_memory=False,**kw)
def save_json(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def integers(s):
    good=s.str.fullmatch(r'\d+(?:\.0+)?')
    v=pd.to_numeric(s.where(good),errors='coerce')
    return v.map(lambda x:str(int(x)) if pd.notna(x) else '')
def flag(s):
    unknown=set(s)-{'','0','1','Yes','No'}
    if unknown:raise ValueError(('Unexpected flag values',unknown))
    return s.map({'0':'FALSE','1':'TRUE','Yes':'TRUE','No':'FALSE','':''})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ingest-downloads',type=Path)
    ap.add_argument('--baseline-dir',type=Path,default=DATA)
    ap.add_argument('--promote',action='store_true');args=ap.parse_args()
    Q.mkdir(parents=True,exist_ok=True)
    if args.ingest_downloads:
        for src in sorted(args.ingest_downloads.glob('SRFF_20??_AS_OF_*.csv')):
            year=src.name.split('_')[1];dest=S/year/'SRFF'/src.name;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert sha(dest)==sha(src),f'Existing source differs: {dest}'
            else:shutil.copy2(src,dest)
        src=args.ingest_downloads/'Data_Dictionary_AS_OF_20260903_JB.xlsx'
        dest=S/'docs/source_metadata'/src.name;dest.parent.mkdir(exist_ok=True)
        if dest.exists():assert sha(dest)==sha(src)
        else:shutil.copy2(src,dest)
    baseline=sorted(args.baseline_dir.glob('WA_crashes_harmonized_*.csv'))
    assert len(baseline)==10,'Expected ten baseline annual files (2017–2026)'
    # Reject enriched input: a baseline is required for deterministic provenance.
    for path in baseline:
        sample=read(path,nrows=3)
        assert not sample.pipeline_version.str.contains(REV,regex=False).any(), 'Already enriched: rerun from qa/revisions/'+REV+'/baseline/data'
    BACK.mkdir(exist_ok=True);(BACK/'data').mkdir(exist_ok=True)
    for path in baseline:
        target=BACK/'data'/path.name
        if not target.exists():shutil.copy2(path,target)
    oldqa=P/'qa/post_harmonization/WA'
    if not (BACK/'post_harmonization').exists():shutil.copytree(oldqa,BACK/'post_harmonization')
    stage=Q/'staged';stage.mkdir(exist_ok=True)
    fields=list(csv.DictReader((P/'config/canonical_crash_schema.csv').open(encoding='utf-8-sig')))
    fields=[r['field_name'] for r in fields]
    xwalk=read(P/'config/enrichment/WA_SRFF_crosswalk.csv')
    maps={field:dict(zip(g.source_label,g.canonical_value)) for field,g in xwalk.groupby('source_field')}
    manners=dict(zip(xwalk.loc[xwalk.source_field.eq('FIRST COLLISION TYPE / OBJECT STRUCK'),'source_label'],xwalk.loc[xwalk.source_field.eq('FIRST COLLISION TYPE / OBJECT STRUCK'),'manner_code']))
    summary=[];allids=set();source_manifest=[]
    baseline_id_year={}
    for path in baseline:
        yr=int(path.stem.split('_')[-1])
        for cid in read(path,usecols=['source_crash_id']).source_crash_id:
            assert cid not in baseline_id_year,'Duplicate baseline report number'
            baseline_id_year[cid]=yr
    tracked=['severity_kabco','manner_of_collision_mmucc','road_surface_condition','fatalities','injuries','alcohol_involved','drug_involved','speeding_involved','work_zone_related','posted_speed_limit','latitude','longitude']
    for path in baseline:
        year=int(path.stem.split('_')[-1]);a=read(path)
        assert list(a.columns)==fields and a.source_crash_id.ne('').all() and a.source_crash_id.is_unique
        a=a.set_index('source_crash_id',drop=False); old=a.copy();old_ids=set(a.index)
        srff=list((S/str(year)/'SRFF').glob('SRFF_*.csv'));assert len(srff)<=1
        n=None;inputsha=None;joined=0;newids=[];cross_year_excluded=0;srff_source_rows=0
        # CAT Minor demonstrably mixes B and C. Preserve its raw label, never
        # assign a precise grade where the detailed source is absent.
        minor=a.severity_raw_label.eq('Minor')
        a.loc[minor,'severity_kabco']='U'
        a.loc[minor,'severity_provenance']='INJURY_PRESENT_SEVERITY_UNSPECIFIED'
        # CAT ObjectStruck does not establish event order. The old heuristic
        # also misread guardrail as train and defaulted arbitrary text to fixed
        # objects. Preserve the source label; withdraw unsupported first-event
        # and partner assertions. Detailed SRFF first-event values replace them.
        for col in ['first_harmful_event','first_harmful_event_group','first_harmful_event_raw_code','collision_partner_group']:
            a[col]=''
        a['first_harmful_event_provenance']=np.where(a.first_harmful_event_raw_label.ne(''),'OBJECT_STRUCK_EVENT_ORDER_UNSPECIFIED','UNAVAILABLE')
        # CAT commercial involvement is a boolean, not a vehicle count.
        a.loc[a.commercial_vehicle_involved.eq('TRUE'),'commercial_vehicle_count']=''
        if srff:
            src=srff[0];inputsha=sha(src);source_manifest.append({'path':str(src),'sha256':inputsha,'year':year})
            n=read(src,skiprows=1,encoding='cp1252');n['REPORT NUMBER']=n['REPORT NUMBER'].str.strip()
            assert n['REPORT NUMBER'].ne('').all() and n['REPORT NUMBER'].is_unique
            n['_source_row']=[str(i) for i in range(1,len(n)+1)]
            n=n.set_index('REPORT NUMBER',drop=False)
            srff_source_rows=len(n)
            cross=np.asarray(n.index.map(lambda cid:cid in baseline_id_year and baseline_id_year[cid]!=year),dtype=bool)
            cross_year_excluded=int(cross.sum())
            if cross_year_excluded:
                exceptions=n.loc[cross,['REPORT NUMBER','DATE','_source_row']].copy()
                exceptions['retained_CAT_year']=exceptions.index.map(baseline_id_year)
                exceptions['resolution']='RETAIN_EXISTING_CAT_ID_AND_YEAR; SRFF_ALTERNATE_DATE_RETAINED_IN_RAW; NO_SECOND_CRASH_CREATED'
                exceptions.to_csv(stage/f'WA_cross_year_id_conflicts_{year}.csv',index=False,encoding='utf-8-sig')
                n=n.loc[~cross].copy()
            dates=pd.to_datetime(n.DATE,format='%m/%d/%Y',errors='raise')
            assert dates.dt.year.eq(year).all()
            times=pd.to_datetime(n['24 HR TIME'],format='%H:%M',errors='raise').dt.strftime('%H:%M:%S')
            common=n.index.intersection(a.index);newids=list(n.index.difference(a.index,sort=False));joined=len(common)
            a=a.reindex(a.index.append(pd.Index(newids))).fillna('')
            for c,v in [('state','WA'),('crash_year',str(year)),('date_precision','DAY'),('time_precision','MINUTE'),('coordinate_status','MISSING'),('severity_provenance','UNAVAILABLE'),('manner_provenance','UNAVAILABLE'),('functional_class_provenance','UNAVAILABLE'),('speeding_provenance','UNAVAILABLE')]:a.loc[newids,c]=v
            a.loc[newids,'source_crash_id']=newids;a.loc[newids,'crash_uid']=['WA:'+s for s in newids]
            a.loc[newids,'crash_date']=dates.loc[newids].dt.strftime('%Y-%m-%d')
            a.loc[newids,'crash_month']=dates.loc[newids].dt.month.astype(str)
            a.loc[newids,'crash_time']=times.loc[newids]
            a.loc[newids,'crash_datetime']=a.loc[newids,'crash_date']+'T'+a.loc[newids,'crash_time']
            for target,source in [('county','COUNTY'),('city','CITY')]:a.loc[newids,target]=n.loc[newids,source]
            # Keep CAT date/time and coordinates for linked incidents; snapshots
            # may disagree. All SRFF alternate values remain in raw/extended data.
            for target,source,prefix in [('severity_kabco','MOST SEVERE INJURY TYPE','severity'),('weather','WEATHER','weather'),('light_condition','LIGHTING CONDITIONS','light'),('road_surface_condition','ROAD SURFACE CONDITIONS','road_surface')]:
                labels=n[source];unknown=set(labels)-set(maps[source])- {''}
                assert not unknown,(year,source,unknown)
                out=labels.map(maps[source]).fillna('')
                take=out.ne('')
                # Explicit unknown should not displace a known CAT classification.
                informative=~out.isin(['U','UNKNOWN'])
                missing=a.loc[n.index,target].isin(['','U','UNKNOWN'])
                ids=n.index[take & (informative | missing)]
                a.loc[ids,target]=out.loc[ids]
                a.loc[ids,prefix+'_raw_code']=labels.loc[ids]
                a.loc[ids,prefix+'_raw_label']=labels.loc[ids]
                a.loc[ids,prefix+'_provenance']='CROSSWALK_SRFF'
            # Exact crash-level reported counts. Injuries exclude fatalities.
            for target,source in [('fatalities','TOTAL FATALITIES'),('vehicles','TOTAL VEHICLES'),('pedestrian_count','TOTAL PEDESTRIANS INVOLVED'),('bicyclist_count','TOTAL BICYCLISTS INVOLVED')]:
                values=integers(n[source]);assert values.ne('').all(),(year,source)
                a.loc[n.index,target]=values
            parts=[integers(n[c]) for c in ['TOTAL SERIOUS INJURIES','TOTAL MINOR INJURIES','TOTAL POSSIBLE INJURIES']]
            assert all(v.ne('').all() for v in parts)
            a.loc[n.index,'injuries']=sum(v.astype(int) for v in parts).astype(str)
            # A positive fatality count establishes K if the label is inconsistent.
            fatalids=n.index[a.loc[n.index,'fatalities'].astype(int).gt(0)]
            corrected=fatalids[a.loc[fatalids,'severity_kabco'].ne('K')]
            a.loc[corrected,'severity_kabco']='K';a.loc[corrected,'severity_provenance']='DERIVED_SRFF_FATALITIES'
            a.loc[n.index,'vehicles_raw']=n['TOTAL VEHICLES'];a.loc[n.index,'vehicles_minimum']=a.loc[n.index,'vehicles'];a.loc[n.index,'vehicles_precision']='EXACT'
            for kind in ['pedestrian','bicyclist']:
                a.loc[n.index,kind+'_involved']=np.where(a.loc[n.index,kind+'_count'].astype(int).gt(0),'TRUE','FALSE')
            label=n['FIRST COLLISION TYPE / OBJECT STRUCK'];assert set(label)<=set(maps['FIRST COLLISION TYPE / OBJECT STRUCK'])
            group=label.map(maps['FIRST COLLISION TYPE / OBJECT STRUCK']).fillna('');manner=label.map(manners).fillna('')
            a.loc[n.index,'first_harmful_event_raw_code']=label;a.loc[n.index,'first_harmful_event_raw_label']=label
            a.loc[n.index,'first_harmful_event']=group;a.loc[n.index,'first_harmful_event_group']=group
            a.loc[n.index,'first_harmful_event_provenance']=np.where(group.ne(''),'CROSSWALK_SRFF','UNRESOLVED_CODE')
            partners=['MOTOR_VEHICLE_IN_TRANSPORT','PEDESTRIAN','PEDALCYCLIST','ANIMAL','PARKED_VEHICLE','FIXED_OBJECT','TRAIN','OTHER_NON_FIXED_OBJECT']
            a.loc[n.index,'collision_partner_group']=group.where(group.isin(partners),'')
            a.loc[n.index,'manner_raw_code']=label;a.loc[n.index,'manner_raw_label']=label
            a.loc[n.index,'manner_of_collision_mmucc']=manner
            a.loc[n.index,'manner_provenance']=np.where(manner.ne(''),'CROSSWALK_SRFF','UNRESOLVED_CODE')
            for target,source in [('alcohol_involved','TZ Alcohol Impaired Involved Person Indicator'),('drug_involved','TZ Drug Impaired Involved Person Indicator'),('speeding_involved','TZ Speeding Driver Indicator'),('work_zone_related','TZ Work Zone Related Collision Indicator'),('intersection_related','TZ Intersection Related Collision Indicator'),('school_bus_related','TZ School Bus Involved Indicator'),('hit_and_run','HIT & RUN')]:a.loc[n.index,target]=flag(n[source])
            a.loc[n.index,'speeding_provenance']='REPORTED_SRFF'
            # Alcohol involvement includes reported drinking as well as the
            # narrower alcohol-impaired indicator; retain both in the raw file.
            drink=flag(n['TZ Drinking Involved Person Indicator'])
            impaired=flag(n['TZ Alcohol Impaired Involved Person Indicator'])
            a.loc[n.index,'alcohol_involved']=np.where(drink.eq('TRUE')|impaired.eq('TRUE'),'TRUE',np.where(drink.eq('FALSE')&impaired.eq('FALSE'),'FALSE','UNKNOWN'))
            a.loc[n.index,'work_zone_type']=n.WORKZONE.map({'Within WorkZone':'WITHIN_WORK_ZONE','In External Traffic Backup Ca':'TRAFFIC_BACKUP','':''}).fillna('')
            # One shared crash-level speed only if every involved vehicle is
            # represented and all reported positive limits agree.
            speeds=pd.concat([pd.to_numeric(n[f'VEH {i} POSTED SPEED'],errors='coerce').where(lambda v:v.gt(0)&v.le(100)) for i in range(1,4)],axis=1)
            vehicles=pd.to_numeric(n['TOTAL VEHICLES'])
            complete=vehicles.between(1,3)
            for i in range(3):complete &= (vehicles.le(i)|speeds.iloc[:,i].notna())
            applicable=speeds.where(np.arange(3)<vehicles.to_numpy()[:,None])
            agree=complete&applicable.nunique(axis=1).eq(1)
            a.loc[n.index,'posted_speed_limit']=''
            a.loc[n.index[agree],'posted_speed_limit']=applicable.loc[agree].max(axis=1).astype(int).astype(str)
            # TZ motorcycle aggregates include mopeds/scooters; do not relabel
            # that aggregate as an exact motorcycle-only count.
            types=n[[f'VEH {i} TYPE' for i in range(1,4)]]
            motorcycle=types.eq('Motorcycle').sum(axis=1)
            known=vehicles.between(0,3)
            for i in range(3):known &= vehicles.le(i)|~types.iloc[:,i].isin(['','Not Stated','Other'])
            broadzero=n['TZ Motorcycle Collision Indicator'].eq('0')
            a.loc[n.index[motorcycle.gt(0)],'motorcycle_involved']='TRUE'
            a.loc[n.index[broadzero],'motorcycle_involved']='FALSE'
            a.loc[n.index[broadzero],'motorcycle_count']='0'
            a.loc[n.index[known],'motorcycle_count']=motorcycle.loc[known].astype(str)
            a.loc[n.index[known],'motorcycle_involved']=np.where(motorcycle.loc[known].gt(0),'TRUE','FALSE')
            a.loc[n.index,'source_schema_id']='WA_CAT_SRFF_2026_10_15'
            a.loc[newids,'source_file']=str(src.relative_to(ROOT/'States')).replace('\\','/')
            a.loc[newids,'source_row_number']=n.loc[newids,'_source_row']
            # Full 307 source columns are retained unchanged in States. This
            # smaller extension preserves concepts without a canonical column.
            extras=['REPORT NUMBER','DATE','24 HR TIME','NON-REPORTABLE','TARGET ZERO Reportable Indicator','TZ Distracted Driver Indicator','TZ Motorcycle Collision Indicator','TZ Total Motorcycles Involved Count','TZ Heavy Vehicle Crash Indicator','TZ Heavy Vehicle Crash Count','SECOND COLLISION TYPE / OBJECT STRUCK','JUNCTION RELATIONSHIP','WORKZONE','WA STATE PLANE SOUTH - X','WA STATE PLANE SOUTH - Y']+[f'VEH {i} POSTED SPEED' for i in range(1,4)]
            ext=n[[c for c in extras if c in n]].copy();ext.insert(0,'crash_uid','WA:'+n['REPORT NUMBER'])
            ext['srff_source_file']=str(src.relative_to(ROOT/'States')).replace('\\','/');ext['srff_data_row']=n['_source_row']
            ext['xy_crs_status']='STATE_PLANE_SOUTH_FEET_DATUM_UNCONFIRMED_NOT_PROMOTED'
            ext.to_csv(stage/f'WA_SRFF_extended_attributes_{year}.csv',index=False,encoding='utf-8-sig',lineterminator='\n')
        a['pipeline_version']=a.pipeline_version.map(lambda s:(s or '0.2.0')+'+'+REV)
        # Alignment is explicit so the original rows/order and additional IDs
        # cannot accidentally disappear during an inner join.
        assert old_ids <= set(a.index) and len(a)==len(old)+len(newids)
        assert len(set(a.index)&allids)==0,'Cross-year duplicate report number'
        allids.update(a.index)
        assert a.crash_uid.eq('WA:'+a.source_crash_id).all()
        assert a.crash_date.str.startswith(str(year)).all()
        assert a.severity_kabco.isin(['K','A','B','C','O','U','']).all()
        assert a.manner_of_collision_mmucc.isin(['0','1','2','6','7','8','9','10','11','99','']).all()
        valid=a.coordinate_status.eq('VALID')
        lat=pd.to_numeric(a.latitude,errors='coerce');lon=pd.to_numeric(a.longitude,errors='coerce')
        assert (lat[valid].between(45.4,49.1)&lon[valid].between(-124.9,-116.8)).all()
        assert a.loc[~valid,['latitude','longitude']].eq('').all().all()
        fat=pd.to_numeric(a.fatalities,errors='coerce');assert a.loc[fat.gt(0),'severity_kabco'].eq('K').all()
        for c in ['fatalities','injuries','vehicles','pedestrian_count','bicyclist_count','motorcycle_count','commercial_vehicle_count']:
            assert (a[c].eq('')|a[c].str.fullmatch(r'\d+')).all(),c
        out=stage/path.name;a[fields].to_csv(out,index=False,encoding='utf-8-sig',lineterminator='\n')
        reread=read(out);assert len(reread)==len(a) and list(reread.columns)==fields
        # Compact cell-level audit: one JSON record per changed accident.
        oldaligned=old.reindex(a.index).fillna('');changed={c:a[c].ne(oldaligned[c]) for c in fields}
        with gzip.open(stage/f'WA_cell_changes_{year}.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as audit:
            before=oldaligned.to_dict('index');after=a.to_dict('index')
            for cid in a.index:
                changes={c:[before[cid][c],after[cid][c]] for c in fields if before[cid][c]!=after[cid][c]}
                if changes:
                    detail={'crash_uid':'WA:'+cid,'change_type':'UPDATED' if cid in old_ids else 'ADDED','changes':changes}
                    if n is not None and cid in n.index:detail.update(srff_source_file=str(srff[0]),srff_data_row=n.at[cid,'_source_row'])
                    audit.write(json.dumps(detail,ensure_ascii=False,separators=(',',':'))+'\n')
        counts=lambda df:{c:int((~df[c].isin(['','U','UNKNOWN'])).sum()) for c in tracked}
        rec=dict(year=year,baseline_rows=len(old),srff_rows=srff_source_rows,cross_year_id_matches_not_duplicated=cross_year_excluded,matched=joined,added=len(newids),output_rows=len(a),baseline_sha256=sha(path),output_sha256=sha(out),srff_sha256=inputsha,coverage_before=counts(old),coverage_after=counts(a),severity_counts=a.severity_kabco.value_counts().to_dict(),manner_counts=a.manner_of_collision_mmucc.value_counts().to_dict(),changed_cells={c:int(v.sum()) for c,v in changed.items()},unresolved_c09=int(a.manner_provenance.eq('UNRESOLVED_CODE').sum()),result='PASS')
        if n is not None:
            ids=n.index.intersection(old.index)
            rec['date_conflicts_retained_CAT']=int((old.loc[ids,'crash_date']!=pd.to_datetime(n.loc[ids,'DATE'],format='%m/%d/%Y').dt.strftime('%Y-%m-%d')).sum())
            rec['time_conflicts_retained_CAT']=int((old.loc[ids,'crash_time'].str[:5]!=pd.to_datetime(n.loc[ids,'24 HR TIME'],format='%H:%M').dt.strftime('%H:%M')).sum())
        summary.append(rec);save_json(Q/'revision_report.json',{'revision':REV,'status':'STAGED','years':summary})
        print(json.dumps({k:rec[k] for k in ['year','baseline_rows','srff_rows','added','output_rows','result']}),flush=True)
        del a,old,oldaligned,reread,before,after,n
    dictionary=S/'docs/source_metadata/Data_Dictionary_AS_OF_20260903_JB.xlsx'
    source_manifest.append({'path':str(dictionary),'sha256':sha(dictionary)})
    report={'revision':REV,'status':'VALIDATED','years':summary,'total_before':sum(r['baseline_rows'] for r in summary),'total_after':sum(r['output_rows'] for r in summary),'source_manifest':source_manifest,'crosswalk_sha256':sha(P/'config/enrichment/WA_SRFF_crosswalk.csv'),'script_sha256':sha(Path(__file__)),'coordinate_policy':'Existing CAT coordinates retained. SRFF XY retained, not transformed until datum is documented.','result':'PASS'}
    save_json(Q/'revision_report.json',report)
    if args.promote:
        # All ten staged annual outputs pass before the first replacement.
        # Copy to a sibling temporary file and atomically replace each file.
        for rec in summary:
            src=stage/f"WA_crashes_harmonized_{rec['year']}.csv";target=DATA/src.name
            tmp=target.with_suffix('.csv.promoting');shutil.copy2(src,tmp);tmp.replace(target)
        extdir=P/'data/extensions/WA';extdir.mkdir(parents=True,exist_ok=True)
        for src in stage.glob('WA_SRFF_extended_attributes_*.csv'):shutil.copy2(src,extdir/src.name)
        manifest=read(oldqa/'harmonization_summary.csv')
        for rec in summary:
            ix=manifest.year.eq(str(rec['year']));manifest.loc[ix,'output_rows']=str(rec['output_rows']);manifest.loc[ix,'output_sha256']=rec['output_sha256']
            # CAT source + SRFF source - CAT duplicates - cross-source overlap
            # - original exclusions = union output. Retain separate components.
            original_source_rows=int(manifest.loc[ix,'source_rows'].iloc[0])
            original_duplicates=int(manifest.loc[ix,'duplicate_source_rows'].iloc[0])
            manifest.loc[ix,'cat_source_rows']=str(original_source_rows)
            manifest.loc[ix,'srff_source_rows']=str(rec['srff_rows'])
            manifest.loc[ix,'srff_linked_rows']=str(rec['matched'])
            manifest.loc[ix,'source_rows']=str(original_source_rows+rec['srff_rows'])
            manifest.loc[ix,'duplicate_source_rows']=str(original_duplicates+rec['matched'])
            manifest.loc[ix,'excluded_source_rows']=str(int(manifest.loc[ix,'excluded_source_rows'].iloc[0])+rec['cross_year_id_matches_not_duplicated'])
            manifest.loc[ix,'revision_manifest']=str(Q/'revision_report.json')
            manifest.loc[ix,'schema_id']='WA_CAT_SRFF_2026_10_15' if rec['srff_rows'] else 'WA_CAT_2017_2026'
            manifest.loc[ix,'unresolved_manner_rows']=str(rec['unresolved_c09'])
        manifest.to_csv(oldqa/'harmonization_summary.csv',index=False,encoding='utf-8-sig',lineterminator='\n')
        report['status']='PROMOTED';save_json(Q/'revision_report.json',report)
        save_json(oldqa/'srff_revision_manifest.json',report)
    print(json.dumps({k:report[k] for k in ['status','total_before','total_after','result']}),flush=True)
if __name__=='__main__':main()
