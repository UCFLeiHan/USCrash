"""Read-only city-label annual crash trends and an independent CPD source comparison."""
from pathlib import Path
import pandas as pd,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';P=U/'qa/Chicago_temporal_2026-10-16';P.mkdir(exist_ok=True)
rows=[];months=[];sources=[]
cols=['crash_uid','crash_date','city','severity_kabco','fatalities','injuries','latitude','longitude','coordinate_status']
for f in sorted((U/'data/crash/IL').glob('IL_crashes_harmonized_*.csv')):
 y=int(f.stem.rsplit('_',1)[1]);d=pd.read_csv(f,dtype=str,keep_default_na=False,usecols=cols);state_n=len(d);d=d.loc[d.city.str.strip().str.casefold().eq('chicago')].copy();assert d.crash_uid.is_unique
 dt=pd.to_datetime(d.crash_date,errors='coerce');k=pd.to_numeric(d.fatalities,errors='coerce');inj=pd.to_numeric(d.injuries,errors='coerce');sev=d.severity_kabco;fatal=sev.eq('K');injury=sev.isin(['A','B','C']);serious=sev.eq('A');valid=d.coordinate_status.eq('VALID')&pd.to_numeric(d.latitude,errors='coerce').between(-90,90)&pd.to_numeric(d.longitude,errors='coerce').between(-180,180)
 rows.append(dict(year=y,crashes=len(d),fatal_crashes=int(fatal.sum()),serious_injury_crashes=int(serious.sum()),injury_crashes=int(injury.sum()),pdo_crashes=int(sev.eq('O').sum()),unknown_severity=int((~sev.isin(['K','A','B','C','O'])).sum()),fatalities=int(k.sum()),injured_people=int(inj.sum()),fatality_count_available=int(k.notna().sum()),injury_count_available=int(inj.notna().sum()),valid_coordinates=int(valid.sum()),date_min=str(dt.min().date()),date_max=str(dt.max().date()),months_present=int(dt.dt.month.nunique()),state_records=state_n))
 for m,z in d.assign(month=dt.dt.month).groupby('month'):
  months.append(dict(year=y,month=int(m),crashes=len(z),fatal_crashes=int(z.severity_kabco.eq('K').sum()),serious_injury_crashes=int(z.severity_kabco.eq('A').sum())))
 sources.append(dict(file=str(f),size=f.stat().st_size,mtime_ns=f.stat().st_mtime_ns));print(rows[-1],flush=True)
a=pd.DataFrame(rows);a['year_on_year_pct']=a.crashes.pct_change()*100;a['injury_crash_pct']=100*a.injury_crashes/a.crashes;a['fatal_crashes_per1000']=1000*a.fatal_crashes/a.crashes;a['K_A_crashes_per1000']=1000*(a.fatal_crashes+a.serious_injury_crashes)/a.crashes
a.to_csv(P/'annual_chicago_idot.csv',index=False);pd.DataFrame(months).to_csv(P/'monthly_chicago_idot.csv',index=False)
# CPD data remain separate; do not append or treat different reporting populations as duplicates.
cpd=[]
for y in range(2013,2027):
 f=R/f'Cities/Chicago/{y}/CPD_crashes.csv'
 if not f.exists():continue
 header=pd.read_csv(f,nrows=0).columns.tolist();date=next((c for c in header if c.lower()=='crash_date'),None)
 if not date:continue
 ids=next((c for c in header if c.lower()=='crash_record_id'),None);fields=[date]+([ids] if ids else [])
 d=pd.read_csv(f,usecols=fields,dtype=str,keep_default_na=False);dt=pd.to_datetime(d[date],format='mixed',errors='coerce')
 cpd.append(dict(year=y,records=len(d),unique_ids=int(d[ids].nunique()) if ids else None,date_min=str(dt.min()),date_max=str(dt.max()),months_present=int(dt.dt.month.nunique())));print('CPD',cpd[-1],flush=True)
c=pd.DataFrame(cpd);c.to_csv(P/'cpd_separate_source_coverage.csv',index=False);a[['year','crashes']].merge(c,on='year',how='outer').to_csv(P/'idot_cpd_comparison.csv',index=False)
plt.rcParams.update({'font.family':'Arial','font.size':10,'pdf.fonttype':42,'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,3,figsize=(13,3.7),layout='constrained');x=a.year
axs[0].plot(x,a.crashes/1000,'o-',color='#286090',lw=2,ms=4);axs[0].set_ylabel('Recorded crashes (thousands)');axs[0].set_title('(a) All recorded crashes',loc='left')
axs[1].plot(x,a.fatal_crashes,'o-',color='#b33a3a',lw=2,ms=4);axs[1].set_ylabel('Fatal crashes');axs[1].set_title('(b) Fatal crashes',loc='left')
axs[2].plot(x,a.injury_crash_pct,'o-',color='#6a51a3',lw=2,ms=4);axs[2].set_ylabel('Injury crashes / all crashes (%)');axs[2].set_title('(c) Nonfatal injury crash share',loc='left')
for ax in axs:
 ax.set_xticks(list(x)[::2]);ax.tick_params(axis='x',rotation=45);ax.set_xlabel('Year');ax.grid(axis='y',alpha=.18);ax.axvspan(2019.5,2020.5,color='#bbbbbb',alpha=.15,zorder=-1)
for ext in ['png','pdf','svg']:fig.savefig(P/f'chicago_annual_trends.{ext}',dpi=300,bbox_inches='tight')
plt.close(fig)
(P/'manifest.json').write_text(json.dumps({'inputs':sources,'unit':'Crash record','selection':'Canonical city label equals Chicago, case insensitive; missing-coordinate records retained; no city-boundary filter.','annual_population':'IDOT state source2014–2025; CPD municipal source separately checked, never merged.','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2))
print('DONE',P,flush=True)
