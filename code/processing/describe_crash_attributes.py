"""Read-only, reproducible crash attribute diagnostics for a common year.

Uses variable-specific reviewed state/year gates, scans every selected record,
and exports aggregated counts, plots and a local report. No source or canonical
crash values are altered. Calendar-day correction is not traffic exposure.
"""
from __future__ import annotations
import argparse,calendar,collections,hashlib,html,json,sys
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd

U=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')
READY=U/'qa/analysis_readiness_2026-10-14/state_year_variable_readiness.csv'
VERSION='attributes_v2'
SEV=['O','C','B','A','K','U','MISSING']
MANNER=['0','1','2','6','7','8','9','10','11','99','MISSING']
BAD={'','UNKNOWN','UNAVAILABLE','NOT_REPORTED','UNRESOLVED_CODE','SOURCE_UNKNOWN','NOT_APPLICABLE','UNSPECIFIED'}
BADPROV={'SOURCE_MISSING','UNAVAILABLE','UNRESOLVED_CODE',''}
COLS=['crash_uid','crash_year','crash_month','crash_date','crash_time','time_precision',
      'severity_kabco','severity_provenance','manner_of_collision_mmucc','manner_provenance',
      'weather','light_condition','road_surface_condition']
ML={'0':'非与运输中机动车碰撞（0）','1':'追尾／前后相撞（1）','2':'正面相撞（2）','6':'角度相撞（6）',
    '7':'同向擦碰（7）','8':'反向擦碰（8）','9':'尾部与侧面相撞（9）','10':'尾部与尾部相撞（10）',
    '11':'其他（11）','99':'未知（99）','MISSING':'未提供／缺失'}
SL={'O':'O 无伤','C':'C 可能受伤','B':'B 轻伤','A':'A 重伤','K':'K 死亡','U':'U 未细分／未知','MISSING':'源缺失'}
SC=['#507b98','#8cb8c1','#d8bc78','#d68d53','#b55151','#aaaeb5','#e1e4e8']
WEEK=['周一','周二','周三','周四','周五','周六','周日']

def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def scan_state(task):
    state,year,out=task;out=Path(out)
    source=U/f'data/crash/{state}/{state}_crashes_harmonized_{year}.csv'
    sig={'name':source.name,'size':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns,'version':VERSION}
    cache=out/'cache'/f'{state}.json'
    if cache.exists():
        old=json.loads(cache.read_text(encoding='utf-8'))
        if old['input_signature']==sig:return old
    r=dict(state=state,year=year,input_signature=sig,input_file=str(source),source_rows=0,rows=0,
           outside_year=0,date_missing=0,time_missing=0,calendar_month_disagreement=0,
           month=[0]*12,weekday=[0]*7,hour=[0]*24,weekday_hour=np.zeros((7,24),dtype=np.int64).tolist(),
           severity={},manner={},weather={},light_condition={},road_surface_condition={},time_precision={},
           severity_hour=np.zeros((len(SEV),24),dtype=np.int64).tolist(),
           severity_weekday=np.zeros((len(SEV),7),dtype=np.int64).tolist(),
           manner_hour=np.zeros((len(MANNER),24),dtype=np.int64).tolist(),
           exact_midnight=0,fine_time_rows=0,minute_zero=0,second_zero=0,
           declared_second_rows=0,declared_second_zero=0)
    wh=np.zeros((7,24),dtype=np.int64);sh=np.zeros((len(SEV),24),dtype=np.int64)
    sw=np.zeros((len(SEV),7),dtype=np.int64);mh=np.zeros((len(MANNER),24),dtype=np.int64)
    counters={k:collections.Counter() for k in ['severity','manner','weather','light_condition','road_surface_condition','time_precision']}
    for d in pd.read_csv(source,usecols=COLS,dtype=str,keep_default_na=False,chunksize=120000):
        r['source_rows']+=len(d)
        year_ok=d.crash_year.eq(str(year));r['outside_year']+=int((~year_ok).sum());d=d.loc[year_ok].copy()
        r['rows']+=len(d)
        date=pd.to_datetime(d.crash_date,format='%Y-%m-%d',errors='coerce')
        assert date.dropna().dt.year.eq(year).all(),(state,'date/canonical year disagreement')
        mo=pd.to_numeric(d.crash_month,errors='coerce');valid_m=mo.between(1,12)
        r['calendar_month_disagreement']+=int((date.notna()&date.dt.month.ne(mo)).sum())
        assert r['calendar_month_disagreement']==0,(state,'month disagrees with valid date')
        dow=date.dt.dayofweek;valid_d=date.notna();r['date_missing']+=int((~valid_d).sum())
        hour=pd.to_numeric(d.crash_time.str[:2],errors='coerce')
        valid_h=d.crash_time.str.fullmatch(r'\d{2}:\d{2}:\d{2}')&hour.between(0,23)&d.time_precision.ne('DATE')
        r['time_missing']+=int((~valid_h).sum())
        for key,s,n in [('month',mo[valid_m],12),('weekday',dow[valid_d],7),('hour',hour[valid_h],24)]:
            counts=s.astype(int).value_counts()
            for k,v in counts.items():r[key][int(k)-(1 if key=='month' else 0)]+=int(v)
        both=valid_d&valid_h
        np.add.at(wh,(dow[both].astype(int).to_numpy(),hour[both].astype(int).to_numpy()),1)
        sev=d.severity_kabco.where(d.severity_kabco.isin(SEV),'U')
        sev=sev.mask(d.severity_kabco.eq('')|d.severity_provenance.isin(BADPROV),'MISSING')
        manner=d.manner_of_collision_mmucc
        assert manner.isin(MANNER+['']).all(),(state,'unexpected C09 code')
        manner=manner.mask(manner.eq('')|d.manner_provenance.isin(BADPROV),'MISSING')
        for k,s in [('severity',sev),('manner',manner),('weather',d.weather),
                    ('light_condition',d.light_condition),('road_surface_condition',d.road_surface_condition),
                    ('time_precision',d.time_precision)]:counters[k].update(s.value_counts().to_dict())
        si=pd.Categorical(sev,categories=SEV).codes;mi=pd.Categorical(manner,categories=MANNER).codes
        np.add.at(sh,(si[valid_h],hour[valid_h].astype(int).to_numpy()),1)
        np.add.at(sw,(si[valid_d],dow[valid_d].astype(int).to_numpy()),1)
        np.add.at(mh,(mi[valid_h],hour[valid_h].astype(int).to_numpy()),1)
        fine=d.time_precision.isin(['MINUTE','SECOND'])&valid_h
        r['fine_time_rows']+=int(fine.sum())
        r['exact_midnight']+=int((fine&d.crash_time.eq('00:00:00')).sum())
        r['minute_zero']+=int((fine&d.crash_time.str[3:5].eq('00')).sum())
        r['second_zero']+=int((fine&d.crash_time.str[6:8].eq('00')).sum())
        declared=d.time_precision.eq('SECOND')&valid_h
        r['declared_second_rows']+=int(declared.sum())
        r['declared_second_zero']+=int((declared&d.crash_time.str[6:8].eq('00')).sum())
    for k,c in counters.items():r[k]=dict(c)
    for k,a in [('weekday_hour',wh),('severity_hour',sh),('severity_weekday',sw),('manner_hour',mh)]:r[k]=a.tolist()
    assert sum(r['severity'].values())==sum(r['manner'].values())==r['rows']
    assert sum(r['month'])==r['rows'],(state,'missing month')
    assert sum(r['weekday'])+r['date_missing']==r['rows']
    assert sum(r['hour'])+r['time_missing']==r['rows']
    dump(cache,r);return r

def extract_tables(results,ready,out,year):
    by={r['state']:r for r in results};cohorts={}
    for key in ['season','weekday','hour','fine_kabco','c09']:
        cohorts[key]=ready.loc[ready[key+'_candidate'],'state'].tolist()
    tables={};categories=[];quality=[];flags=[]
    for r in results:
        st=r['state'];n=r['rows'];fine_n=r['fine_time_rows'];h=np.array(r['hour'])
        fine=sum(r['severity'].get(k,0) for k in SEV[:5]);known=sum(r['manner'].get(k,0) for k in MANNER[:9])
        q=dict(state=st,source_rows=r['source_rows'],analysis_rows=n,removed_outside_calendar_year=r['outside_year'],
               exact_date_rate=1-r['date_missing']/n,time_rate=1-r['time_missing']/n,
               fine_kabco_rate=fine/n,c09_known_rate=known/n,
               midnight_clock_share=h[0]/h.sum() if h.sum() else None,
               exact_midnight_share_of_fine_times=r['exact_midnight']/fine_n if fine_n else None,
               fine_time_count=fine_n,minute_zero_share=r['minute_zero']/fine_n if fine_n else None,
               second_zero_share=r['second_zero']/fine_n if fine_n else None,
               declared_second_count=r['declared_second_rows'],
               declared_second_zero_share=r['declared_second_zero']/r['declared_second_rows'] if r['declared_second_rows'] else None,
               midnight_to_neighbors=h[0]/max(1,(h[23]+h[1])/2))
        for field in ['weather','light_condition','road_surface_condition']:
            q[field+'_known_rate']=sum(v for k,v in r[field].items() if k.upper() not in BAD)/n
        quality.append(q)
        if fine_n>1000 and q['exact_midnight_share_of_fine_times']>.06 and q['midnight_to_neighbors']>3:
            flags.append(dict(state=st,flag='MIDNIGHT_SPIKE_REVIEW',value=q['exact_midnight_share_of_fine_times'],
                              meaning='Fine-tagged exact midnight values are concentrated; inspect raw unknown-time conventions. This is not proof of invalid records.'))
        if r['declared_second_rows']>1000 and q['declared_second_zero_share']>.99:
            flags.append(dict(state=st,flag='SECOND_TAG_PRECISION_REVIEW',value=q['declared_second_zero_share'],
                              meaning='SECOND-tagged values mostly end :00; source measurement precision may be coarser than the exported timestamp. MINUTE-tagged values are not flagged for their expected zero seconds.'))
        for field in ['severity','manner','weather','light_condition','road_surface_condition','time_precision']:
            for cat,v in r[field].items():categories.append(dict(state=st,variable=field,category=cat,records=v,share_all_state_records=v/n))
        for variable,countkey,size in [('season','month',12),('weekday','weekday',7),('hour','hour',24)]:
            for k,v in enumerate(r[countkey]):tables.setdefault(countkey,[]).append(dict(state=st,bin=k+1 if countkey=='month' else k,records=v,candidate=st in cohorts[variable]))
    for k,v in tables.items():pd.DataFrame(v).to_csv(out/f'{k}_by_state.csv',index=False,encoding='utf-8-sig')
    cat=pd.DataFrame(categories);cat.to_csv(out/'categorical_counts_by_state.csv',index=False,encoding='utf-8-sig')
    quality=pd.DataFrame(quality).set_index('state');quality.to_csv(out/'state_quality.csv',encoding='utf-8-sig')
    pd.DataFrame(flags,columns=['state','flag','value','meaning']).to_csv(out/'diagnostic_flags.csv',index=False,encoding='utf-8-sig')
    ready.to_csv(out/'cohort_selection.csv',index=False,encoding='utf-8-sig')
    def counts(key,field,labels):return np.array([[by[st][field].get(k,0) for k in labels] for st in cohorts[key]],dtype=float)
    def matrix(key,field):return np.array([by[st][field] for st in cohorts[key]],dtype=float)
    monthly=matrix('season','month');weekly=matrix('weekday','weekday');hourly=matrix('hour','hour')
    days=np.array([calendar.monthrange(year,m)[1] for m in range(1,13)])
    dates=pd.date_range(f'{year}-01-01',f'{year}-12-31');wdays=np.bincount(dates.dayofweek,minlength=7)
    mdaily=monthly/days;wdaily=weekly/wdays
    mindex=mdaily/(monthly.sum(axis=1)/len(dates))[:,None]
    windex=wdaily/(weekly.sum(axis=1)/len(dates))[:,None]
    pd.DataFrame(mindex,index=cohorts['season'],columns=range(1,13)).to_csv(out/'monthly_calendar_corrected_index.csv',encoding='utf-8-sig')
    joint_wh=sorted(set(cohorts['weekday'])&set(cohorts['hour']))
    wh=sum((np.array(by[st]['weekday_hour']) for st in joint_wh),start=np.zeros((7,24),dtype=np.int64))
    joint_sh=sorted(set(cohorts['fine_kabco'])&set(cohorts['hour']))
    sh=sum((np.array(by[st]['severity_hour']) for st in joint_sh),start=np.zeros((len(SEV),24),dtype=np.int64))
    joint_mh=sorted(set(cohorts['c09'])&set(cohorts['hour']))
    mh=sum((np.array(by[st]['manner_hour']) for st in joint_mh),start=np.zeros((len(MANNER),24),dtype=np.int64))
    for name,v,labels in [('weekday_hour_counts',wh,WEEK),('severity_hour_counts',sh,SEV),('manner_hour_counts',mh,MANNER)]:
        pd.DataFrame(v,index=labels,columns=range(24)).to_csv(out/f'{name}.csv',encoding='utf-8-sig')
    sever=counts('fine_kabco','severity',SEV);mann=counts('c09','manner',MANNER)
    pooled_m=mdaily.sum(axis=0)/(monthly.sum()/len(dates));pooled_w=wdaily.sum(axis=0)/(weekly.sum()/len(dates))
    pooled_h=hourly.sum(axis=0)/hourly.sum()*100
    seasons=[]
    for label,ix in [('冬季（1/2/12月）',[0,1,11]),('春季（3–5月）',[2,3,4]),('夏季（6–8月）',[5,6,7]),('秋季（9–11月）',[8,9,10])]:
        n=int(monthly[:,ix].sum());caldays=int(days[ix].sum())
        seasons.append(dict(season=label,records=n,calendar_days=caldays,
            records_per_calendar_day=n/caldays,relative_to_annual_day=(n/caldays)/(monthly.sum()/len(dates))))
    pd.DataFrame(seasons).to_csv(out/'seasonal_counts.csv',index=False,encoding='utf-8-sig')
    # Unknown and unavailable values stay in denominators in the main category charts.
    sev_share=sever.sum(axis=0)/sever.sum()*100;man_share=mann.sum(axis=0)/mann.sum()*100
    known_h=sh[:5].sum(axis=0);ka=sh[3:5].sum(axis=0)/np.maximum(1,known_h)*100
    night=list(range(6))+list(range(18,24));day=list(range(6,18))
    kn=lambda hh:float(sh[3:5,hh].sum()/sh[:5,hh].sum()*100)
    environment={}
    for field in ['weather','light_condition','road_surface_condition']:
        sts=quality.index[quality[field+'_known_rate'].ge(.9)].tolist();c=collections.Counter()
        for st in sts:c.update(by[st][field])
        environment[field]=dict(states=sts,counts=dict(c),total=sum(c.values()))
    summary=dict(year=year,source_population_states=list(by),source_records=sum(r['source_rows'] for r in results),
       calendar_year_records=sum(r['rows'] for r in results),outside_year_records=sum(r['outside_year'] for r in results),
       cohorts={k:dict(states=v,jurisdictions=len(v),records=sum(by[s]['rows'] for s in v)) for k,v in cohorts.items()},
       monthly_peak=int(pooled_m.argmax()+1),monthly_low=int(pooled_m.argmin()+1),
       monthly_peak_index=float(pooled_m.max()),monthly_low_index=float(pooled_m.min()),
       weekday_peak=WEEK[int(pooled_w.argmax())],weekday_low=WEEK[int(pooled_w.argmin())],
       weekday_peak_index=float(pooled_w.max()),weekday_low_index=float(pooled_w.min()),
       hourly_peak=int(pooled_h.argmax()),hourly_peak_share=float(pooled_h.max()),
       morning_peak=int(np.argmax(pooled_h[6:10])+6),afternoon_peak=int(np.argmax(pooled_h[15:19])+15),
       severity_pct=dict(zip(SEV,sev_share)),manner_pct=dict(zip(MANNER,man_share)),
       ka_share_night=kn(night),ka_share_day=kn(day),severity_hour_states=joint_sh,weekday_hour_states=joint_wh,
       manner_hour_states=joint_mh,environment=environment,diagnostic_flags=flags,
       interpretation='Counts/shares of collected eligible crashes, not nationally representative estimates or exposure-adjusted risk')
    suspect={r['state'] for r in flags if r['flag']=='MIDNIGHT_SPIKE_REVIEW'}
    common=set(ready.loc[ready.joint_field_rate_candidate,'state'])
    sensitivity=[]
    for name,allowed in [('主分析：各变量分别选州',set(by)),
                         ('敏感性：排除零点尖峰提示州',set(by)-suspect),
                         ('敏感性：五项字段率共同通过州',common)]:
        hs=[st for st in cohorts['hour'] if st in allowed];ss=[st for st in joint_sh if st in allowed]
        ms=[st for st in cohorts['season'] if st in allowed]
        hv=sum((np.array(by[st]['hour']) for st in hs),start=np.zeros(24,dtype=np.int64))
        sv=sum((np.array(by[st]['severity_hour']) for st in ss),start=np.zeros((len(SEV),24),dtype=np.int64))
        mv=sum((np.array(by[st]['month']) for st in ms),start=np.zeros(12,dtype=np.int64))/days
        assert hs and ss and ms
        sensitivity.append(dict(analysis=name,hour_jurisdictions=len(hs),severity_hour_jurisdictions=len(ss),
            month_jurisdictions=len(ms),hour_peak=int(hv.argmax()),hour_peak_share=float(hv.max()/hv.sum()*100),
            month_peak=int(mv.argmax()+1),ka_night=float(sv[3:5,night].sum()/sv[:5,night].sum()*100),
            ka_day=float(sv[3:5,day].sum()/sv[:5,day].sum()*100)))
    pd.DataFrame(sensitivity).to_csv(out/'cohort_sensitivity.csv',index=False,encoding='utf-8-sig')
    summary['cohort_sensitivity']=sensitivity;summary['midnight_review_states']=sorted(suspect)
    dump(out/'summary.json',summary)
    return dict(by=by,cohorts=cohorts,quality=quality,cat=cat,monthly=monthly,weekly=weekly,hourly=hourly,
        mdaily=mdaily,mindex=mindex,windex=windex,pooled_m=pooled_m,pooled_w=pooled_w,pooled_h=pooled_h,
        sever=sever,mann=mann,sev_share=sev_share,man_share=man_share,wh=wh,sh=sh,mh=mh,ka=ka,
        days=days,wdays=wdays,seasons=seasons,summary=summary)

def render(d,out,year):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
    figures=[];cards=[];C=d['cohorts'];summary=d['summary'];blue='#2c7197';orange='#cb884b'
    def save(fig,name,title,subtitle):
        fig.suptitle(title,fontsize=19,fontweight='bold',x=.07,ha='left',y=.995)
        subtitle_y=.925 if fig.get_size_inches()[1]<=8 else .952
        fig.text(.07,subtitle_y,subtitle,fontsize=10,color='#526373',ha='left')
        fig.text(.07,.012,f'{year}候选州样本；各图使用各自字段门槛。日历校正不等于交通暴露量校正；分布相似不证明数据准确。',fontsize=9,color='#607080')
        fig.savefig(out/f'{name}.png',dpi=190,bbox_inches='tight');figures.append(fig);cards.append((name,title))
    def line(ax,x,y,title,xlabels=None,reference=None):
        ax.plot(x,y,marker='o',color=blue,lw=2,ms=4);ax.set_title(title,loc='left',fontsize=12,pad=12)
        if xlabels is not None:ax.set_xticks(x,xlabels)
        ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
        if reference is not None:ax.axhline(reference,color='#929da7',ls='--',lw=1)
    def categories(ax,vals,labels,title):
        order=np.arange(len(vals));ax.barh(order,vals,color=[blue if i<len(vals)-2 else '#aeb6be' for i in order])
        ax.set_yticks(order,labels);ax.invert_yaxis();ax.set_xlabel('占所选样本的比例（%，含未知/缺失）');ax.set_title(title,loc='left',fontsize=12)
        ax.set_xlim(0,max(vals)*1.24)
        for i,v in enumerate(vals):ax.text(v+max(vals)*.015,i,f'{v:.2f}%',va='center',fontsize=9)
    fig,axs=plt.subplots(2,3,figsize=(17,10));fig.subplots_adjust(top=.87,bottom=.10,wspace=.42,hspace=.50)
    line(axs[0,0],range(1,13),d['pooled_m'],f'月份｜{len(C["season"])}个辖区',reference=1);axs[0,0].set_ylabel('按月天数校正的相对频数');axs[0,0].set_xticks(range(1,13))
    line(axs[0,1],range(7),d['pooled_w'],f'星期｜{len(C["weekday"])}个辖区',WEEK,1);axs[0,1].set_ylabel('按该星期天数校正的相对频数')
    line(axs[0,2],range(24),d['pooled_h'],f'小时｜{len(C["hour"])}个辖区');axs[0,2].set_xticks(range(0,24,3));axs[0,2].set_ylabel('有时刻事故中的占比（%）')
    categories(axs[1,0],d['sev_share'],[SL[s] for s in SEV],f'伤情｜{len(C["fine_kabco"])}个辖区')
    top=[0,1,2,3,4,8,9,10]
    labels=[ML[MANNER[i]] for i in top];labels[0]='非与运输中机动车\n碰撞（0）';vals=d['man_share'][top].copy()
    # Merge only the three uncommon rear/side geometries in this overview.
    labels.insert(5,'其他擦碰/尾部形态\n（8/9/10）');vals=np.insert(vals,5,d['man_share'][5:8].sum())
    categories(axs[1,1],vals,labels,f'C09形态｜{len(C["c09"])}个辖区')
    line(axs[1,2],range(24),d['ka'],'同一小时内K+A占已知KABCO比例');axs[1,2].set_ylabel('K+A / 已知KABCO（%）');axs[1,2].set_xticks(range(0,24,3))
    save(fig,'00_overview','事故属性描述性分析：先看实际分布','各变量使用不同候选州集合；横跨图板的比例不可当作同一全国样本比较。')
    fig=plt.figure(figsize=(16,13));gs=fig.add_gridspec(2,2,width_ratios=[1,1.5],hspace=.40,wspace=.30)
    ax=fig.add_subplot(gs[0,0]);sx=fig.add_subplot(gs[1,0]);bx=fig.add_subplot(gs[:,1]);fig.subplots_adjust(top=.89,bottom=.10)
    line(ax,range(1,13),d['pooled_m'],'按事故量合并 vs 每州等权',reference=1)
    ax.plot(range(1,13),d['mindex'].mean(axis=0),color=orange,marker='s',label='每州等权平均');ax.lines[0].set_label('事故量合并')
    ax.fill_between(range(1,13),np.quantile(d['mindex'],.1,axis=0),np.quantile(d['mindex'],.9,axis=0),color=orange,alpha=.14,label='州际10–90%区间')
    ax.set_xticks(range(1,13));ax.set_xlabel('月份');ax.set_ylabel('相对日均事故频数（年度日均=1）');ax.legend(frameon=False)
    sx.bar(range(4),[s['relative_to_annual_day'] for s in d['seasons']],color=[blue,'#84a57e',orange,'#aa7480'])
    sx.set_xticks(range(4),['冬\n1/2/12月','春\n3–5月','夏\n6–8月','秋\n9–11月']);sx.axhline(1,color='#929da7',ls='--',lw=1)
    sx.set_ylabel('相对日均事故频数');sx.set_title('年内季节合计：按天数校正',loc='left');sx.text(0,-.20,'冬季为本日历年1、2、12月的分类合计。',transform=sx.transAxes,color='#607080',fontsize=9)
    order=np.argsort(d['mindex'][:,[0,1,11]].mean(axis=1)-d['mindex'][:,[5,6,7]].mean(axis=1))
    im=bx.imshow(d['mindex'][order],aspect='auto',cmap='RdBu_r',vmin=.55,vmax=1.45)
    bx.set_yticks(range(len(order)),np.array(C['season'])[order]);bx.set_xticks(range(12),range(1,13));bx.set_xlabel('月份');bx.set_title('各州季节性：校正月长后的相对频数',loc='left');fig.colorbar(im,ax=bx,shrink=.55,label='1 = 本州年度日均')
    save(fig,'01_monthly_seasonality','月份与季节性：保留州际差异',f'{len(C["season"])}个辖区；按各月日历天数校正，仍未控制车流、里程、天气暴露或报告门槛。')
    fig,axs=plt.subplots(2,2,figsize=(16,10));fig.subplots_adjust(top=.86,bottom=.10,hspace=.4,wspace=.28)
    line(axs[0,0],range(7),d['pooled_w'],'星期分布：按实际星期天数校正',WEEK,1)
    axs[0,0].plot(range(7),d['windex'].mean(axis=0),color=orange,marker='s',label='每州等权');axs[0,0].lines[0].set_label('事故量合并');axs[0,0].legend(frameon=False)
    line(axs[0,1],range(24),d['pooled_h'],'一天内的事故分布');axs[0,1].set_ylabel('占有时刻事故的比例（%）');axs[0,1].set_xticks(range(0,24,2))
    heat=d['wh']/d['wdays'][:,None];im=axs[1,0].imshow(heat,aspect='auto',cmap='YlOrRd');axs[1,0].set_yticks(range(7),WEEK);axs[1,0].set_xticks(range(0,24,3));axs[1,0].set_title('星期×小时：每个该星期日的平均事故数',loc='left');fig.colorbar(im,ax=axs[1,0],shrink=.8)
    wh=d['wh'];weekday=(wh[:5]/d['wdays'][:5,None]).sum(axis=0)/5;weekend=(wh[5:]/d['wdays'][5:,None]).sum(axis=0)/2
    axs[1,1].plot(range(24),weekday/weekday.sum()*100,label='周一至周五',color=blue,lw=2)
    axs[1,1].plot(range(24),weekend/weekend.sum()*100,label='周六至周日',color=orange,lw=2);axs[1,1].set_xticks(range(0,24,3));axs[1,1].set_ylabel('各自日均小时分布（%）');axs[1,1].set_title('工作日与周末的小时形状',loc='left');axs[1,1].legend(frameon=False)
    save(fig,'02_weekday_hour','星期与小时：区分通勤时段和周末形状',f'星期{len(C["weekday"])}个辖区，小时{len(C["hour"])}个辖区，交叉图使用两者交集；时间为当地时钟。')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(16,14),gridspec_kw={'width_ratios':[.8,1.5]});fig.subplots_adjust(top=.90,bottom=.1,wspace=.38)
    categories(ax,d['sev_share'],[SL[s] for s in SEV],f'细伤情覆盖≥95%的{len(C["fine_kabco"])}个辖区')
    states=sorted(d['by']);mat=np.array([[d['by'][s]['severity'].get(k,0) for k in SEV] for s in states],dtype=float);mat=mat/mat.sum(axis=1)[:,None]*100
    left=np.zeros(len(states))
    for i,k in enumerate(SEV):bx.barh(states,mat[:,i],left=left,label=SL[k],color=SC[i]);left+=mat[:,i]
    bx.invert_yaxis();bx.set_xlabel('占本州全部入选记录的比例（%）');bx.set_title('全部候选州：粗分类/未知必须可见',loc='left');bx.legend(loc='upper center',bbox_to_anchor=(.5,-.04),ncol=3,frameon=False)
    save(fig,'03_severity','严重程度：事故构成与分类缺失分开看','U可能包含笼统受伤、官方未知或无法细分，不能当作无伤；源缺失另列，不补造A/B/C。')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(17,14),gridspec_kw={'width_ratios':[1,1.2]});fig.subplots_adjust(top=.9,bottom=.10,wspace=.45)
    categories(ax,d['man_share'],[ML[k] for k in MANNER],f'C09已知覆盖≥90%的{len(C["c09"])}个辖区')
    q=d['quality'].sort_values('c09_known_rate');bx.barh(q.index,q.c09_known_rate*100,color=[blue if s in C['c09'] else '#b7c0c9' for s in q.index]);bx.axvline(90,color=orange,ls='--');bx.set_xlabel('已知C09覆盖率（%）');bx.set_title('空值/未知不等于没有事故',loc='left')
    save(fig,'04_collision_manner','碰撞形态：保留MMUCC C09含义','代码0包含行人、骑行者、动物、固定物、停放车辆及非碰撞事件等，不可全部称为单车事故。')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(16,8));fig.subplots_adjust(top=.82,bottom=.14,wspace=.3)
    line(ax,range(24),d['ka'],'K+A在各小时已知伤情事故中的比例');ax.set_xticks(range(0,24,3));ax.set_ylabel('K+A / KABCO（%）')
    for code,col in [('1',blue),('6',orange),('0','#74986a'),('2','#aa6274')]:
        vals=d['mh'][MANNER.index(code)];bx.plot(range(24),vals/max(1,vals.sum())*100,label=ML[code],color=col,lw=2)
    bx.set_xticks(range(0,24,3));bx.set_ylabel('各自形态有时刻样本中的比例（%）');bx.set_title('不同碰撞形态的小时形状',loc='left');bx.legend(frameon=False,fontsize=9)
    save(fig,'05_joint_patterns','属性之间是否呈现可解释的关联','左图为已发生事故中的伤情构成，右图各形态分别归一化；均不能解释为每次出行的事故风险或因果效应。')
    fig,axs=plt.subplots(1,3,figsize=(20,8));fig.subplots_adjust(top=.81,bottom=.15,wspace=.55)
    translations={'CLEAR':'晴','CLOUDY':'阴','RAIN':'雨','SNOW':'雪','FOG_SMOKE':'雾/烟/霾','DAYLIGHT':'白天','DARK_LIGHTED':'夜间有照明','DARK_UNLIGHTED':'夜间无照明','DAWN':'黎明','DUSK':'黄昏','DRY':'干燥','WET':'湿润','ICE_FROST':'冰/霜','SLUSH':'雪泥','SNOW_ICE':'冰雪混合'}
    for ax,(field,info) in zip(axs,summary['environment'].items()):
        c=collections.Counter({k:v for k,v in info['counts'].items() if k.upper() not in BAD});top=c.most_common(5)
        rest=sum(c.values())-sum(v for k,v in top);unknown=info['total']-sum(c.values())
        labels=[translations.get(k,k.replace('_',' ')) for k,v in top]+['其余已知类','未知/缺失/不适用'];v=[v/info['total']*100 for k,v in top]+[rest/info['total']*100,unknown/info['total']*100]
        categories(ax,np.array(v),labels,{'weather':'天气','light_condition':'光照','road_surface_condition':'路面'}[field]+f'｜{len(info["states"])}个辖区')
    save(fig,'06_environment','天气、光照与路面：看频数，避免误读风险','每项选择其自身已知字段率≥90%的州；晴天、白天、干燥时事故多，可能主要反映这些条件出现得更多。')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(17,14));fig.subplots_adjust(top=.90,bottom=.1,wspace=.3)
    q=d['quality'].sort_values('exact_midnight_share_of_fine_times',na_position='first');ax.barh(q.index,q.exact_midnight_share_of_fine_times.fillna(0)*100,color=blue)
    for st in q.index[q.exact_midnight_share_of_fine_times.isna()]:ax.text(.12,st,'n/a',va='center',color='#8b939c',fontsize=9)
    ax.axvline(6,color=orange,ls='--');ax.set_xlabel('细时间标签样本中精确00:00:00的比例（%）');ax.set_title('零点堆积只提示复核，不自动删除',loc='left')
    cov=d['quality'][['exact_date_rate','time_rate','fine_kabco_rate','c09_known_rate','weather_known_rate','light_condition_known_rate','road_surface_condition_known_rate']]
    im=bx.imshow(cov,aspect='auto',cmap='YlGnBu',vmin=0,vmax=1);bx.set_yticks(range(len(cov)),cov.index);bx.set_xticks(range(7),['具体日期','时刻','细伤情','C09','天气','光照','路面'],rotation=45,ha='right');bx.set_title('各州字段覆盖率',loc='left');fig.colorbar(im,ax=bx,shrink=.55)
    save(fig,'07_diagnostics','需要追查的分布：零点、时间精度与缺失','6%是复核提示阈值；n/a表示无细时间标签。小时区间的整点表达是合法编码，缺失和异常均保留。')
    with PdfPages(out/'crash_attribute_descriptives.pdf') as pdf:
        for fig in figures:pdf.savefig(fig,bbox_inches='tight')
    for fig in figures:plt.close(fig)
    return cards

def report(d,cards,out,year):
    s=d['summary'];quality=d['quality'];e=s['environment']
    known=lambda f,k:100*e[f]['counts'].get(k,0)/max(1,e[f]['total'])
    findings=[f'日历天数校正后的合并月度频数：{s["monthly_peak"]}月最高（年度日均的{s["monthly_peak_index"]:.2f}倍），{s["monthly_low"]}月最低（{s["monthly_low_index"]:.2f}倍）。',
       f'星期频数：{s["weekday_peak"]}最高，{s["weekday_low"]}最低，已校正各星期在{year}年的出现次数。',
       f'小时峰值为{s["hourly_peak"]:02d}:00–{s["hourly_peak"]:02d}:59，占有时刻样本{s["hourly_peak_share"]:.2f}%；6–9时段内峰值{s["morning_peak"]}时，15–18时段内峰值{s["afternoon_peak"]}时。',
       f'细伤情候选州中O无伤占{s["severity_pct"]["O"]:.2f}%，K死亡占{s["severity_pct"]["K"]:.2f}%；未知与源缺失仍在分母中。',
       f'C09候选州中前后相撞/追尾占{s["manner_pct"]["1"]:.2f}%，角度相撞占{s["manner_pct"]["6"]:.2f}%；代码0占{s["manner_pct"]["0"]:.2f}%，含多类事故对象，不能统称单车。',
       f'同一组伤情×时刻候选州中，18:00–05:59的K+A比例为{s["ka_share_night"]:.2f}%，06:00–17:59为{s["ka_share_day"]:.2f}%。这是已发生事故的构成，不是暴露量校正风险。',
       f'各自环境变量候选样本中：晴天{known("weather","CLEAR"):.2f}%、白天{known("light_condition","DAYLIGHT"):.2f}%、干燥路面{known("road_surface_condition","DRY"):.2f}%。三个分母不同，不能推断晴天/白天/干燥更危险。',
       f'敏感性检查：排除零点尖峰提示州后，小时峰值仍为{s["cohort_sensitivity"][1]["hour_peak"]}时；五项字段共同达标的{s["cohort_sensitivity"][2]["hour_jurisdictions"]}州中，小时峰仍为{s["cohort_sensitivity"][2]["hour_peak"]}时，月度峰则为{s["cohort_sensitivity"][2]["month_peak"]}月。主样本的{s["monthly_peak"]}月峰值受到选州构成影响。']
    text=['# 事故属性描述性分析','',f'年份：{year}。实际读取{len(d["by"])}个辖区、{s["source_records"]:,}条记录；去除归档年与事故年不符的{s["outside_year_records"]:,}条后，本分析范围{s["calendar_year_records"]:,}条。源数据和正式统一表均未修改。',
          '', '## 实测结果','']+['- '+f for f in findings]
    text+=['','## 样本与分母','', '|变量|辖区数|入选州记录总数|','|---|---:|---:|']
    for k,v in s['cohorts'].items():text.append(f'|{k}|{v["jurisdictions"]}|{v["records"]:,}|')
    text+=['','上述记录总数不等于每项有效观测数，具体分布只计算该变量有效记录。分类图把U、未知及源缺失明确展示。',
       '', '## 不能用“符合常识”替代验证','',
       '- 来源覆盖、报告门槛、城市/乡村构成及缺失机制不同，合并样本不是全国代表性估计。按事故量合并与每州等权结果同时展示。',
       '- 月份和星期只校正日历天数。未校正AADT、VMT、小时车流量或天气持续时长，不输出因果结论。',
       '- 当前分析是2023年横截面；不能推断其他年份的规律，更不能将疫情或来源切换当作真实趋势。',
       '- 星期由实际完整日期计算；PA、NM及OH部分年度日号不足，不补造星期。所有2026 YTD及已知部分年度不混入。',
       '- 伤情只按已统一的KABCO及出处使用；未知与笼统受伤不强拆A/B/C。细伤情不足州仍在诊断图中显示。',
       '- C09代码0保留广义含义。首次有害事件、碰撞对象与C09不互相冒充。',
       '- 零点与整点堆积可能来自未知值默认编码、真实行为或区间表示；diagnostic_flags.csv是复核清单，未据此删除事故。',
       '- SECOND标签不等于源信息真的精确到秒。对细时间标签检查秒位为00的比例；区间时间另行复核区间宽度。',
       '- 环境类别图使用现有规范类别，少数低频类仅在图中合并为“其余已知类”；全量类别逐州计数仍保留。',
       '', '## 外部参考与复现','',
       '- NHTSA Traffic Safety Facts 2023: https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813738 。用于参考变量含义与全国统计语境；没有把本地非代表性样本与全国估计强行配平。',
       '- 运行：python scripts/describe_crash_attributes.py --year 2023 --workers 2；若仅改图使用 --plots-only。',
       '- state_quality.csv、cohort_selection.csv、categorical_counts_by_state.csv、各时间分布CSV、交叉计数CSV以及summary.json提供图表的底层汇总。',
       '- 以manifest.json中的输入路径、SHA-256和脚本版本追溯；cache按输入文件大小、修改时间及算法版本失效。']
    text+=['','## 样本选择敏感性','',
           '只改变本轮分析样本，不删除正式事故记录。零点提示州：'+', '.join(s['midnight_review_states'])+'。',
           '|分析|小时辖区数|小时峰值|夜间K+A占比|日间K+A占比|月度峰值|','|---|---:|---:|---:|---:|---:|']
    for row in s['cohort_sensitivity']:
        text.append(f'|{row["analysis"]}|{row["hour_jurisdictions"]}|{row["hour_peak"]}时|{row["ka_night"]:.2f}%|{row["ka_day"]:.2f}%|{row["month_peak"]}月|')
    if s['diagnostic_flags']:
        text+=['','## 自动提示（不是已确认错误）','']
        for r in s['diagnostic_flags']:text.append(f'- {r["state"]}: {r["flag"]}, {r["value"]:.2%}。{r["meaning"]}')
    (out/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>事故属性描述性分析</title><style>body{font-family:"Microsoft YaHei",sans-serif;max-width:1450px;margin:30px auto;padding:0 24px;background:#f3f6fa;color:#213547}p,li{line-height:1.8}section{background:white;margin:24px 0;padding:24px;border-radius:10px}img{width:100%}a{color:#256b91}h1{font-size:30px}table{border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ddd}</style>'
    page+=f'<h1>{year}年事故属性描述性分析</h1><p>{len(d["by"])}个辖区候选范围 · {s["calendar_year_records"]:,}条当年记录；各变量另按字段覆盖选州。</p><p>图形是所收集事故的频数与构成；不代表全国普查、暴露量校正风险或数据准确性认证。</p>'
    page+='<p><a href="crash_attribute_descriptives.pdf">全部图件PDF</a> · <a href="README.md">方法和发现</a> · <a href="state_quality.csv">逐州质量</a> · <a href="cohort_selection.csv">样本选择</a> · <a href="diagnostic_flags.csv">待核查提示</a></p><section><h2>实测结果</h2><ul>'
    page+=''.join('<li>'+html.escape(f)+'</li>' for f in findings)+'</ul></section>'
    page+='<section><h2>样本选择敏感性</h2><p>只改变分析样本，未删除正式事故记录。AK的精确零点集中需要复核；下表检验它是否改变主要规律。</p>'
    tab=pd.DataFrame(s['cohort_sensitivity'])[['analysis','hour_jurisdictions','hour_peak','ka_night','ka_day','month_peak']].copy()
    tab.columns=['分析','小时辖区数','小时峰值','夜间K+A占比（%）','日间K+A占比（%）','月度峰值']
    page+=tab.to_html(index=False,float_format=lambda x:f'{x:.2f}')+'</section>'
    for name,title in cards:page+=f'<section><h2>{title}</h2><a href="{name}.png"><img src="{name}.png" alt="{title}"></a></section>'
    (out/'index.html').write_text(page,encoding='utf-8')
    return findings

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,default=2023);ap.add_argument('--workers',type=int,default=2);ap.add_argument('--plots-only',action='store_true');args=ap.parse_args()
    year=args.year;out=U/f'qa/attribute_descriptives_{year}_2026-10-14';(out/'cache').mkdir(parents=True,exist_ok=True)
    ready=pd.read_csv(READY);ready=ready[(ready.year.eq(year))&ready.population_coverage_gate].copy()
    assert not ready.empty
    tasks=[(st,year,str(out)) for st in ready.state]
    if args.plots_only:
        results=[]
        for task in tasks:
            st=task[0];r=json.loads((out/'cache'/f'{st}.json').read_text(encoding='utf-8'))
            source=Path(r['input_file']);sig=r['input_signature']
            assert source.stat().st_size==sig['size'] and source.stat().st_mtime_ns==sig['mtime_ns'],'stale cache'
            assert sig['version']==VERSION;results.append(r)
    else:
        results=[]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(scan_state,t):t[0] for t in tasks}
            for f in as_completed(futures):
                r=f.result();results.append(r);print(f'{r["state"]}: {r["rows"]:,} calendar-year records ({len(results)}/{len(tasks)})',flush=True)
    results.sort(key=lambda r:r['state'])
    for r in results:
        assert r['source_rows']==int(ready.loc[ready.state.eq(r['state']),'records'].iloc[0])
        # Tie every analyzed file to the actual bytes of the formal release.
        if 'input_sha256' not in r:
            r['input_sha256']=digest(Path(r['input_file']))
            dump(out/'cache'/f'{r["state"]}.json',r)
        manifest=pd.read_csv(U/f'qa/post_harmonization/{r["state"]}/harmonization_summary.csv')
        expected=manifest.loc[manifest.year.eq(year),'output_sha256'].iloc[0]
        assert r['input_sha256']==expected,(r['state'],'formal file hash mismatch')
    d=extract_tables(results,ready,out,year);cards=render(d,out,year);findings=report(d,cards,out,year)
    dump(out/'manifest.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),script_version=VERSION,
         script_sha256=digest(Path(__file__)),selection_sha256=digest(READY),raw_or_canonical_data_modified=False,
         aggregate_cache_files=len(results),year=year,inputs=[dict(file=r['input_file'],sha256=r['input_sha256'],**r['input_signature']) for r in results],
         field_rate_thresholds={'date_time_severity':.95,'manner':.9,'environment':.9},
         findings=findings,result='PASS'))
    print('\n'.join(findings),flush=True);print('Report:',out/'index.html',flush=True)

if __name__=='__main__':main()
