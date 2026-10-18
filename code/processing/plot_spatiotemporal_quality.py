"""Read-only, full-record spatiotemporal diagnostics for the formal crash CSVs.

No crash values are modified. Counts refer to available records, not exposure-
adjusted risk. Census boundaries are used for an independent spatial screen.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = (Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')
OUT = ROOT / 'qa' / 'spatiotemporal_review_2026-10-14'
COLS = ['crash_uid','crash_date','crash_year','crash_month','date_precision',
        'crash_time','time_precision','latitude','longitude','coordinate_status',
        'severity_kabco','severity_provenance','manner_of_collision_mmucc',
        'manner_provenance','weather','light_condition','road_surface_condition',
        'first_harmful_event','source_schema_id']
VERSION = 'spacetime_v1'
BAD = {'', 'UNKNOWN', 'UNAVAILABLE', 'NOT_REPORTED', 'UNRESOLVED_CODE', 'SOURCE_UNKNOWN'}
BOUNDARY_URL = 'https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_500k.zip'


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def geometry_context():
    import geopandas as gpd
    g = gpd.read_file(OUT/'reference/us_states_census_2023.zip').to_crs(4326)
    conus = g[~g.STUSPS.isin(['AK','HI','PR','VI','GU','MP','AS'])].to_crs(5070)
    b = conus.total_bounds
    step = 5000
    origin = np.floor(b[:2]/step)*step-step
    top = np.ceil(b[2:]/step)*step+step
    return g, {'origin': origin.tolist(), 'step':step,
               'nx':int((top[0]-origin[0])/step), 'ny':int((top[1]-origin[1])/step)}


def scan_state(st):
    import shapely
    from pyproj import Transformer
    g, grid = geometry_context()
    target = g.loc[g.STUSPS.eq(st), 'geometry'].iloc[0]
    # A 2 km buffer is only an independent flag, never an automatic correction.
    epsg = 3338 if st == 'AK' else 5070
    projected = g[g.STUSPS.eq(st)].to_crs(epsg).geometry.iloc[0]
    from shapely.ops import transform
    to_local = Transformer.from_crs(4326, epsg, always_xy=True)
    buffered = projected.buffer(2000)
    shapely.prepare(buffered)
    files = sorted((ROOT/'data/crash'/st).glob('*_crashes_harmonized_*.csv'))
    signature = [(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in files]
    cache = OUT/'cache'/f'{st}.json'
    if cache.exists():
        old = json.loads(cache.read_text(encoding='utf-8'))
        if old.get('version')==VERSION and old.get('signature')==[list(x) for x in signature]:
            return old
    hist = np.zeros(grid['nx']*grid['ny'],dtype=np.int64)
    hist23 = hist.copy()
    annual, monthly, hourly, daily, precision = [], [], [], [], []
    outside_examples = []
    state_dates = collections.Counter()
    for p in files:
        y = int(p.stem.rsplit('_',1)[1])
        a = dict(state=st,year=y,rows=0,valid_coordinates=0,missing_coordinates=0,
                 out_of_bounds_coordinates=0,invalid_coordinates=0,
                 polygon_outside_2km=0,coordinate_numeric_disagreement=0,
                 exact_date=0,month_available=0,time_available=0,
                 severity_observed=0,severity_specific_kabco=0,manner_known=0,
                 weather_known=0,light_known=0,road_surface_known=0,fhe_known=0,
                 calendar_year_mismatch=0,midnight_time=0)
        months=collections.Counter(); hours=collections.Counter(); dates=collections.Counter()
        ps=collections.Counter(); schemas=collections.Counter(); sev=collections.Counter()
        for d in pd.read_csv(p,usecols=COLS,dtype=str,keep_default_na=False,chunksize=180000):
            n=len(d);a['rows']+=n
            def count(key,mask): a[key]+=int(np.count_nonzero(mask))
            cs=d.coordinate_status
            for val,key in [('VALID','valid_coordinates'),('MISSING','missing_coordinates'),
                            ('OUT_OF_BOUNDS','out_of_bounds_coordinates'),('INVALID','invalid_coordinates')]:
                count(key,cs.eq(val))
            lat=pd.to_numeric(d.latitude,errors='coerce').to_numpy(dtype=float)
            lon=pd.to_numeric(d.longitude,errors='coerce').to_numpy(dtype=float)
            numeric=np.isfinite(lat)&np.isfinite(lon)&(np.abs(lat)<=90)&(np.abs(lon)<=180)
            valid=cs.eq('VALID').to_numpy()&numeric
            count('coordinate_numeric_disagreement',cs.eq('VALID').to_numpy()&~numeric)
            if np.any(valid):
                x,z=to_local.transform(lon[valid],lat[valid])
                good=shapely.contains_xy(buffered,x,z)
                count('polygon_outside_2km',~good)
                ix=np.flatnonzero(valid)[~good]
                for k in ix[:max(0,8-len(outside_examples))]:
                    outside_examples.append(dict(state=st,year=y,crash_uid=d.crash_uid.iloc[k],
                                                 longitude=float(lon[k]),latitude=float(lat[k])))
                if st!='AK':
                    px=np.floor((np.asarray(x)-grid['origin'][0])/grid['step']).astype(int)
                    py=np.floor((np.asarray(z)-grid['origin'][1])/grid['step']).astype(int)
                    inside=(px>=0)&(px<grid['nx'])&(py>=0)&(py<grid['ny'])
                    index=py[inside]*grid['nx']+px[inside]
                    h=np.bincount(index,minlength=hist.size)
                    hist+=h
                    if y==2023: hist23+=h
            has_date=d.crash_date.str.fullmatch(r'\d{4}-\d{2}-\d{2}')
            count('exact_date',has_date)
            observed_month=pd.to_numeric(d.crash_month,errors='coerce')
            month_ok=observed_month.between(1,12)
            count('month_available',month_ok)
            months.update({int(k):int(v) for k,v in observed_month[month_ok].value_counts().items()})
            cy=pd.to_numeric(d.crash_year,errors='coerce')
            count('calendar_year_mismatch',cy.notna() & cy.ne(y))
            has_time=d.crash_time.str.match(r'^\d{2}:\d{2}:\d{2}$')
            count('time_available',has_time)
            count('midnight_time',d.crash_time.eq('00:00:00'))
            hh=pd.to_numeric(d.loc[has_time,'crash_time'].str[:2],errors='coerce')
            hours.update({int(k):int(v) for k,v in hh.value_counts().items() if 0<=k<=23})
            dates.update({str(k):int(v) for k,v in d.loc[has_date,'crash_date'].value_counts().items()})
            ps.update({str(k):int(v) for k,v in d.time_precision.value_counts().items()})
            schemas.update({str(k):int(v) for k,v in d.source_schema_id.value_counts().items()})
            sev.update({str(k):int(v) for k,v in d.severity_kabco.value_counts().items()})
            count('severity_observed',~d.severity_provenance.isin(['SOURCE_MISSING','UNAVAILABLE','UNRESOLVED_CODE','']) & d.severity_kabco.ne(''))
            count('severity_specific_kabco',d.severity_kabco.isin(list('KABCO')))
            count('manner_known',~d.manner_of_collision_mmucc.isin(['','99']) & ~d.manner_provenance.isin(['UNAVAILABLE','UNRESOLVED_CODE','SOURCE_MISSING']))
            for field,key in [('weather','weather_known'),('light_condition','light_known'),
                              ('road_surface_condition','road_surface_known'),('first_harmful_event','fhe_known')]:
                count(key,~d[field].str.upper().isin(BAD))
        valid_dates=[]
        for key,number in dates.items():
            try:
                dt=pd.Timestamp(key)
                valid_dates.append(key)
            except Exception:
                continue
            daily.append(dict(state=st,file_year=y,date=key,rows=number))
        a['first_date']=min(valid_dates) if valid_dates else ''
        a['last_date']=max(valid_dates) if valid_dates else ''
        a['observed_days']=len(valid_dates)
        a['months_with_records']=len(months)
        a['source_schemas']=';'.join(sorted(schemas))
        for key,value in sev.items():a['severity_'+(key or 'BLANK')]=value
        for month in range(1,13):monthly.append(dict(state=st,year=y,month=month,rows=months[month]))
        for hour in range(24):hourly.append(dict(state=st,year=y,hour=hour,rows=hours[hour]))
        for value,number in ps.items():precision.append(dict(state=st,year=y,time_precision=value,rows=number))
        annual.append(a)
        print(f'{st} {y} {a["rows"]:,}',flush=True)
    np.savez_compressed(OUT/'cache'/f'{st}_grid.npz',all=hist,year2023=hist23)
    result=dict(version=VERSION,state=st,signature=signature,annual=annual,
                monthly=monthly,hourly=hourly,daily=daily,precision=precision,
                polygon_examples=outside_examples,grid=grid)
    dump(cache,result)
    return result


def assemble(results):
    frames={}
    for key in ['annual','monthly','hourly','daily','precision','polygon_examples']:
        frame=pd.DataFrame([row for r in results for row in r[key]])
        frame.to_csv(OUT/f'{key}.csv',index=False,encoding='utf-8-sig')
        frames[key]=frame
    a=frames['annual'].sort_values(['state','year']).copy()
    a['previous_rows']=a.groupby('state').rows.shift()
    a['previous_year']=a.groupby('state').year.shift()
    a['yoy_change']=np.where(a.year.sub(a.previous_year).eq(1),a.rows/a.previous_rows-1,np.nan)
    flags=[]
    documented={('FL',2019):'官方本地提取已注明不完整',('TX',2019):'仅12月30–31日',
                ('AL',2025):'实测日期仅1月1日–3月31日',('MA',2001):'仅55条，首年覆盖明显不足，待核对',
                ('MS',2019):'实测日期仅9月3日–12月31日',
                ('NM',2019):'只有年月，无日号',('WY',2025):'较前几年下降；完整性待外部核对'}
    for _,r in a.iterrows():
        reasons=[]
        if r.year==2026:reasons.append('2026进行中年份，不做全年同比')
        if (r.state,int(r.year)) in documented:reasons.append(documented[r.state,int(r.year)])
        if r.state=='OK':reasons.append('KAB/受伤子集，不能当作全事故库')
        if r.months_with_records<12:reasons.append(f'仅{int(r.months_with_records)}个月有记录（提示，非完整性证明）')
        if r.first_date and r.last_date and r.exact_date/r.rows>.95 and r.year<2026:
            first=pd.Timestamp(r.first_date);last=pd.Timestamp(r.last_date)
            if first.year==r.year and last.year==r.year and (first.month>1 or last.month<12):
                reasons.append(f'实测日期窗口{r.first_date}至{r.last_date}，可能是部分年度')
        if pd.notna(r.yoy_change) and abs(r.yoy_change)>.35 and r.year!=2026:
            reasons.append(f'归档年度数量同比{r.yoy_change:+.0%}（可能为覆盖/口径变化）')
        if r.valid_coordinates/r.rows<.8:reasons.append(f'有效坐标{r.valid_coordinates/r.rows:.1%}')
        if r.exact_date/r.rows<.95:reasons.append(f'具体日期{r.exact_date/r.rows:.1%}')
        if r.polygon_outside_2km:reasons.append(f'{int(r.polygon_outside_2km):,}个VALID点在所属州2km缓冲之外')
        if reasons:flags.append(dict(state=r.state,year=int(r.year),rows=int(r.rows),review_reason='；'.join(reasons)))
    pd.DataFrame(flags).to_csv(OUT/'review_flags.csv',index=False,encoding='utf-8-sig')
    s=a.groupby('state').sum(numeric_only=True).drop(columns=['year','previous_year','previous_rows','yoy_change'],errors='ignore')
    s['valid_coordinate_rate']=s.valid_coordinates/s.rows
    s['exact_date_rate']=s.exact_date/s.rows
    s['time_rate']=s.time_available/s.rows
    s['severity_observed_rate']=s.severity_observed/s.rows
    s['specific_kabco_rate']=s.severity_specific_kabco/s.rows
    s['manner_known_rate']=s.manner_known/s.rows
    s.to_csv(OUT/'state_summary.csv',encoding='utf-8-sig')
    totals={k:int(a[k].sum()) for k in ['rows','valid_coordinates','missing_coordinates',
             'invalid_coordinates','out_of_bounds_coordinates','polygon_outside_2km',
             'coordinate_numeric_disagreement','exact_date','time_available','month_available',
             'severity_observed','severity_specific_kabco','manner_known']}
    totals.update(jurisdictions=len(s),annual_files=len(a),snapshot='2026-10-14',
                  reference_year=2023,boundary_url=BOUNDARY_URL,
                  warning='Counts are collected records, not exposure-adjusted risk. State/year coverage differs. Polygon flags are not automatic exclusions.')
    expected=json.loads((ROOT/'qa/cross_state/final_42_state_integrity_audit.json').read_text(encoding='utf-8'))
    assert totals['rows']==expected['total_harmonized_records'],totals['rows']
    assert totals['annual_files']==511
    assert totals['valid_coordinates']+totals['missing_coordinates']+totals['invalid_coordinates']+totals['out_of_bounds_coordinates']==totals['rows']
    dump(OUT/'summary.json',totals)
    return a,s,frames,totals


def plot(a,s,frames,totals):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Rectangle
    import matplotlib.ticker as mtick
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,
                        'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                        'figure.facecolor':'white','axes.titleweight':'bold',
                        'savefig.facecolor':'white'})
    g,grid=geometry_context()
    figures=[]
    def finish(fig,name):
        fig.savefig(OUT/f'{name}.png',dpi=190,bbox_inches='tight')
        figures.append(fig)
    states=sorted(s.index);years=sorted(a.year.unique())
    counts=a.pivot(index='state',columns='year',values='rows').reindex(index=states,columns=years)
    rates=(a.assign(rate=a.valid_coordinates/a.rows).pivot(index='state',columns='year',values='rate').reindex(index=states,columns=years))
    fig,axs=plt.subplots(1,2,figsize=(23,15),gridspec_kw={'wspace':.14})
    cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#e6e9ed')
    im=axs[0].imshow(np.ma.masked_invalid(counts),aspect='auto',cmap=cmap,norm=LogNorm(1000,1e6))
    cmap2=plt.get_cmap('RdYlGn').copy();cmap2.set_bad('#e6e9ed')
    im2=axs[1].imshow(np.ma.masked_invalid(rates),aspect='auto',cmap=cmap2,vmin=0,vmax=1)
    for ax in axs:
        ax.set_yticks(range(len(states)),states)
        ax.set_xticks(range(len(years)),years,rotation=60)
        ax.tick_params(axis='both',length=0)
        ax.set_xlabel('归档年度（部分源年份与日历年份可能不同）')
    axs[0].set_title('A  州—年份事故记录数量（对数色阶）',loc='left',pad=15)
    axs[1].set_title('B  坐标可用率（原管线标记VALID）',loc='left',pad=15)
    fig.colorbar(im,ax=axs[0],fraction=.025,pad=.02,label='已收集事故记录数')
    fig.colorbar(im2,ax=axs[1],fraction=.025,pad=.02,format=mtick.PercentFormatter(1),label='coordinate_status = VALID')
    for st,y in [('FL',2019),('TX',2019),('AL',2025),('MA',2001),('MS',2019)]:
        if st in states and y in years:
            axs[0].add_patch(Rectangle((years.index(y)-.5,states.index(st)-.5),1,1,fill=False,edgecolor='#dd4a33',lw=2))
    fig.suptitle('数据覆盖与空间可用性：41州＋Washington, DC',fontsize=22,y=.99)
    fig.text(.08,.01,'灰色＝无该州年度文件；红框＝部分年度/明显覆盖不足。2026全部为进行中年份；VALID坐标还需独立州界复核。',fontsize=12)
    fig.subplots_adjust(top=.94,bottom=.08)
    finish(fig,'01_state_year_coverage')

    density=np.zeros(grid['nx']*grid['ny'],dtype=np.int64)
    for st in states:
        with np.load(OUT/'cache'/f'{st}_grid.npz') as z:density+=z['year2023']
    conus=g[~g.STUSPS.isin(['AK','HI','PR','VI','GU','MP','AS'])].to_crs(5070)
    a23=a[a.year.eq(2023)].set_index('state')
    geo=conus.merge(a23[['rows','valid_coordinates']],left_on='STUSPS',right_index=True,how='left')
    geo['rate']=geo.valid_coordinates/geo.rows
    fig,(ax,ax2)=plt.subplots(1,2,figsize=(23,10),gridspec_kw={'width_ratios':[1.3,1]})
    conus.plot(ax=ax,color='#edf0f3',edgecolor='#b5bfcb',lw=.5)
    mask=np.ma.masked_where(density.reshape(grid['ny'],grid['nx'])==0,density.reshape(grid['ny'],grid['nx']))
    ext=[grid['origin'][0],grid['origin'][0]+grid['nx']*grid['step'],grid['origin'][1],grid['origin'][1]+grid['ny']*grid['step']]
    im=ax.imshow(mask,origin='lower',extent=ext,cmap='magma_r',norm=LogNorm(1,max(100,int(density.max()))),zorder=3,interpolation='nearest')
    conus.boundary.plot(ax=ax,color='#8f9baa',lw=.4,zorder=4)
    ax.set_title('A  2023年已收集事故：5 km × 5 km网格计数',loc='left')
    fig.colorbar(im,ax=ax,orientation='horizontal',fraction=.035,pad=.025,label='有效坐标事故数／25 km²网格（非暴露量风险）')
    geo.plot(column='rate',ax=ax2,cmap='RdYlGn',vmin=0,vmax=1,edgecolor='white',lw=.7,
             missing_kwds={'color':'#dfe4e9','hatch':'///'})
    for _,r in geo.iterrows():
        if r.STUSPS in ['RI','DE','DC','NJ','CT','MA']:continue
        pt=r.geometry.representative_point()
        label=r.STUSPS+'\n'+(f'{r.rate:.0%}' if pd.notna(r.rate) else '无文件')
        ax2.text(pt.x,pt.y,label,ha='center',va='center',fontsize=8)
    ax2.set_title('B  同年坐标覆盖率：解释地图中的空白',loc='left')
    sm=plt.cm.ScalarMappable(norm=plt.Normalize(0,1),cmap='RdYlGn')
    fig.colorbar(sm,ax=ax2,orientation='horizontal',fraction=.035,pad=.025,format=mtick.PercentFormatter(1),label='有效坐标／该州同年记录数')
    for axx in [ax,ax2]:axx.set_axis_off()
    n23=int(a23.rows.sum());v23=int(a23.valid_coordinates.sum())
    fig.suptitle(f'同年空间分布（2023）：{len(a23)}个辖区，{n23:,}条记录',fontsize=21,y=.98)
    fig.text(.055,.052,f'同年原管线VALID坐标 {v23:,} 条；地图仅绘本土48州＋DC，不显示AK。空白可能是未收集、无坐标或低数量，不能解释为零事故。',fontsize=11)
    fig.text(.055,.025,'底图：US Census 2023 Cartographic Boundary。网格采用EPSG:5070等面积投影；不同州报告口径仍可能不同。',fontsize=10,color='#55616e')
    fig.subplots_adjust(top=.9,bottom=.19,wspace=.08)
    finish(fig,'02_spatial_distribution_2023')

    fig,axs=plt.subplots(7,6,figsize=(23,19),sharex=True)
    for ax,st in zip(axs.flat,states):
        v=a[a.state.eq(st)].sort_values('year')
        full=v[v.year.le(2025)]
        # Missing annual files must break the line instead of implying continuity.
        expanded=full.set_index('year').reindex(range(int(full.year.min()),int(full.year.max())+1))
        ax.plot(expanded.index,expanded.rows/1000,color='#245e9b',lw=1.7,marker='o',markersize=2.6)
        recent=v[v.year.eq(2026)]
        if len(recent):ax.scatter(recent.year,recent.rows/1000,facecolors='none',edgecolors='#e36b35',s=30,lw=1.4)
        for y in [2001,2019,2025]:
            if (st,y) in [('FL',2019),('TX',2019),('AL',2025),('MA',2001),('MS',2019)] and y in v.year.values:
                r=v[v.year.eq(y)].iloc[0];ax.scatter([y],[r.rows/1000],color='#c92a35',s=30,zorder=5)
        ax.set_title(st,loc='left',fontsize=11,pad=2)
        ax.grid(axis='y',alpha=.16);ax.tick_params(labelsize=8)
        ax.set_xlim(2000,2027);ax.set_xticks([2005,2015,2025]);ax.yaxis.set_major_locator(mtick.MaxNLocator(3))
    fig.suptitle('各州年度记录量：寻找断层与来源切换',fontsize=22,y=.995)
    fig.text(.03,.5,'记录数（千；各州纵轴不同）',rotation=90,va='center',fontsize=13)
    fig.text(.065,.013,'蓝线＝已归档年度；橙色空心点＝2026进行中年份；红点＝已知部分年度。年度突变是复核提示，不自动判为数据错误。',fontsize=12)
    fig.subplots_adjust(left=.065,right=.98,top=.96,bottom=.055,hspace=.52,wspace=.35)
    finish(fig,'03_annual_trends_by_state')

    m=frames['monthly'].copy();m=m[m.year.ge(2016)]
    a12=m.groupby(['state','year']).rows.transform('sum')
    m['share']=np.where(a12>0,m.rows/a12,np.nan)
    keys=[(y,k) for y in range(2016,2027) for k in range(1,13)]
    table=m.pivot(index='state',columns=['year','month'],values='share').reindex(index=states,columns=pd.MultiIndex.from_tuples(keys))
    fig,ax=plt.subplots(figsize=(24,14))
    cmap=plt.get_cmap('YlOrRd').copy();cmap.set_bad('#e1e6ec')
    im=ax.imshow(np.ma.masked_invalid(table),aspect='auto',cmap=cmap,vmin=0,vmax=.2)
    ax.set_yticks(range(len(states)),states);ax.set_xticks(np.arange(11)*12+5.5,list(range(2016,2027)))
    for i in range(1,11):ax.axvline(i*12-.5,color='#6e7680',lw=.65)
    ax.tick_params(length=0)
    ax.set_title('月度记录分布：每个州年度内的月份占比',loc='left',fontsize=21,pad=18)
    fig.colorbar(im,ax=ax,fraction=.018,pad=.02,format=mtick.PercentFormatter(1),label='该月份占该州该年记录数的比例（>20%饱和）')
    fig.text(.08,.025,'每一列是一个月（每年1→12月）。白/浅色月＝低数量或零记录；灰色＝无该年度文件或无法获知月份。2026年尾部空缺属YTD。',fontsize=12)
    fig.subplots_adjust(bottom=.075,top=.94)
    finish(fig,'04_monthly_coverage')

    fig,axs=plt.subplots(1,2,figsize=(22,14),gridspec_kw={'wspace':.25})
    metrics=[('valid_coordinate_rate','有效坐标'),('exact_date_rate','具体日号'),('time_rate','有事故时刻'),
             ('severity_observed_rate','源提供严重性'),('specific_kabco_rate','可区分K/A/B/C/O'),('manner_known_rate','已知碰撞形态')]
    mat=s.reindex(states)[[k for k,l in metrics]].to_numpy()
    im=axs[0].imshow(mat,aspect='auto',vmin=0,vmax=1,cmap='RdYlGn')
    axs[0].set_xticks(range(len(metrics)),[l for k,l in metrics],rotation=35,ha='right')
    axs[0].set_yticks(range(len(states)),states)
    for i in range(len(states)):
        for j in range(len(metrics)):
            axs[0].text(j,i,f'{mat[i,j]*100:.0f}',fontsize=8,ha='center',va='center',color='white' if mat[i,j]>.82 or mat[i,j]<.16 else '#1f2933')
    axs[0].set_title('A  关键字段有效覆盖率（%）',loc='left',pad=15)
    pr=frames['precision'].groupby(['state','time_precision']).rows.sum().unstack(fill_value=0).reindex(states).fillna(0)
    colors={'SECOND':'#175b8e','MINUTE':'#3489b8','HOUR':'#f5ad45','HOUR_RANGE':'#d87f2e','DATE':'#c4cbd2','MONTH':'#b7bcc4','MISSING':'#929aa3'}
    left=np.zeros(len(states))
    for col in ['SECOND','MINUTE','HOUR','HOUR_RANGE','DATE','MONTH','MISSING']+[c for c in pr.columns if c not in colors]:
        if col not in pr:continue
        v=pr[col].to_numpy()/s.reindex(states).rows.to_numpy()
        axs[1].barh(np.arange(len(states)),v,left=left,color=colors.get(col,'#929aa3'),label=col,height=.78)
        left+=v
    axs[1].set_yticks(range(len(states)),states);axs[1].invert_yaxis()
    axs[1].xaxis.set_major_formatter(mtick.PercentFormatter(1));axs[1].set_xlim(0,1)
    axs[1].set_title('B  输出中记录的时间精度标签',loc='left',pad=15)
    axs[1].legend(loc='upper center',bbox_to_anchor=(.5,-.055),ncol=3,fontsize=9)
    fig.suptitle('可以用于什么分析：字段可用性与时间精度',fontsize=22,y=.99)
    fig.text(.06,.018,'严重性：排除SOURCE_MISSING等后才计源提供；U不计入具体K/A/B/C/O。碰撞形态：未知99与未解析值不计已知。',fontsize=11)
    fig.subplots_adjust(top=.94,bottom=.13)
    finish(fig,'05_field_quality_and_time_precision')

    fig,(ax,ax2)=plt.subplots(1,2,figsize=(19,9),gridspec_kw={'wspace':.4})
    bad=s[s.polygon_outside_2km>0].sort_values('polygon_outside_2km',ascending=False).head(12).iloc[::-1]
    ax.barh(bad.index,bad.polygon_outside_2km,color='#b94b42',height=.65)
    for st,r in bad.iterrows():
        ax.text(r.polygon_outside_2km,st,f' {int(r.polygon_outside_2km):,}（{r.polygon_outside_2km/max(1,r.valid_coordinates):.2%}）',va='center',fontsize=9)
    ax.set_xlim(0,max(bad.polygon_outside_2km)*1.42)
    ax.set_title('A  标记VALID，但超出所属州界2 km缓冲',loc='left',pad=15)
    ax.set_xlabel('待复核点数（括号为占该州VALID点的比例）')
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    subset=frames['monthly'].query('state in ["AL","FL","MS","TX"] and year in [2019,2025]')
    selected=[('AL',2025),('MS',2019),('FL',2019),('TX',2019)]
    for i,(st,yr) in enumerate(selected):
        v=subset[(subset.state==st)&(subset.year==yr)].sort_values('month')
        ax2.plot(v.month,v.rows,label=f'{st} {yr}',lw=2,marker='o',markersize=4)
    ax2.set_xticks(range(1,13));ax2.set_xlabel('月份');ax2.set_ylabel('已收集事故记录数')
    ax2.set_title('B  已发现的部分年度与提取缺口',loc='left',pad=15)
    ax2.legend(frameon=False);ax2.grid(alpha=.15)
    fig.suptitle('需要优先复核的问题：统计图不是只展示“通过”',fontsize=21,y=.99)
    fig.text(.06,.045,'州界检查是独立筛查，未自动删除或改写坐标；沿海、跨州道路、底图及源地理编码差异均需核对。',fontsize=11)
    fig.text(.06,.018,'右图中缺月不能用零事故解释；FL 2019虽覆盖部分月份，仍是已注明不完整的本地提取。',fontsize=11)
    fig.subplots_adjust(top=.9,bottom=.13)
    finish(fig,'06_priority_quality_checks')

    with PdfPages(OUT/'spatiotemporal_quality_review.pdf') as pdf:
        for fig in figures:pdf.savefig(fig,bbox_inches='tight')
    for fig in figures:plt.close(fig)


def write_report(a,s,frames,t):
    low=s.sort_values('valid_coordinate_rate').head(9)
    changes=a.assign(previous_rows=a.groupby('state').rows.shift(),previous_year=a.groupby('state').year.shift())
    changes['change']=changes.rows/changes.previous_rows-1
    changes=changes[(changes.year<=2025)&(changes.year-changes.previous_year==1)&(changes.change.abs()>.35)]
    text=['# 事故数据时空质量复核','',
          '本报告直接全量扫描正式CSV；未修改任何原始或统一记录。',
          f'共{t["jurisdictions"]}个辖区、{t["annual_files"]}个年度文件、{t["rows"]:,}条事故记录。',
          '', '## 实测覆盖',
          f'- 有效坐标：{t["valid_coordinates"]:,}（{t["valid_coordinates"]/t["rows"]:.2%}）。',
          f'- 有具体日期：{t["exact_date"]:,}（{t["exact_date"]/t["rows"]:.2%}）。',
          f'- 有事故时刻：{t["time_available"]:,}（{t["time_available"]/t["rows"]:.2%}）。',
          f'- VALID坐标经独立州界2km缓冲复核后需检查：{t["polygon_outside_2km"]:,}条。这只是复核标志，未更改记录。',
          '', '## 地理覆盖较低的辖区',
          '|州|记录数|有效坐标|','|---|---:|---:|']
    for st,r in low.iterrows():text.append(f'|{st}|{int(r.rows):,}|{r.valid_coordinate_rate:.1%}|')
    text+=['','## 年度数量异常提示','',
           '数量变化可能来自报告口径、来源切换、疫情、实际变化或不完整提取，需要核对官方年度报告；本报告不把异常自动判为错误。',
           '|州|年度|记录数|较上一归档年度变化|','|---|---:|---:|---:|']
    for _,r in changes.sort_values('change').iterrows():text.append(f'|{r.state}|{int(r.year)}|{int(r.rows):,}|{r.change:+.1%}|')
    text+=['','## 已知限制',
           '- 所有2026年度均未结束；不能与完整年度直接比较。',
           '- FL 2019本地提取已注明不完整；TX 2019仅包含12月30–31日。',
           '- FL 2020–2025已按CODEABLE=Y筛选；早期FDOT源无相同标志，跨来源趋势仍需谨慎。2011–2019误接的首次有害事件已清空，MOST事件保留在修正旁表。',
           '- AL 2025实测截止3月31日；MA 2001只有55条。不得把这些文件当完整年度。',
           '- MS 2019实测日期只覆盖9月3日至12月31日。MO 2024–2025虽12个月都有记录，年度数量显著下降，仍需外部核对。',
           '- OK源为KAB/伤害子集，不是全事故普查。',
           '- NC 2016–2020源为K/A子集，2021以后为不同的全事故公开表；不能把2021的数量跳升解释成真实事故激增。',
           '- ID 2023实测截止10月1日，MO 2003只观测到8个月；均应单列覆盖限制。',
           '- PA与NM不提供日号；保留月份，不用于日级分析。',
           '- NY公开Case表无坐标；MT已按官方EPSG:32100转换XY，NV的EPSG:26911转换已复核。零值和异常点仍保留缺失/异常标记。',
           '- 不同年份和州记录量差异不能直接解释为事故风险；尚未用AADT/VMT/人口进行暴露量归一。',
           '- 时间精度图按现有time_precision元数据统计；秒/分钟标签仍需与原始字段精度独立抽查，不能仅凭字符串格式推断测量精度。',
           '- Census州界复核使用所属州边界的2km投影缓冲；跨州道路、边界精度、官方地理编码及坐标系错误都可能触发。',
           '', '## 可复现与文件',
           '- `annual.csv`、`monthly.csv`、`daily.csv`、`hourly.csv`：全量统计。',
           '- `state_summary.csv`、`review_flags.csv`、`polygon_examples.csv`：筛选与复核清单。',
           '- `01`至`06` PNG与`spatiotemporal_quality_review.pdf`：可分享图件。',
           '- 空单元格与零分别处理；空间密度为EPSG:5070的5km等面积网格精确计数，无抽样。',
           f'- 州界：{BOUNDARY_URL}',
           '- 脚本：`scripts/plot_spatiotemporal_quality.py`。缓存按输入大小、修改时间与脚本版本失效。']
    (OUT/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    cards=[('01_state_year_coverage','州—年份覆盖与坐标率'),('02_spatial_distribution_2023','2023同年空间分布'),
           ('03_annual_trends_by_state','各州年度趋势'),('04_monthly_coverage','月度缺口'),('05_field_quality_and_time_precision','字段覆盖和时间精度'),('06_priority_quality_checks','优先质量复核')]
    html='<!doctype html><meta charset="utf-8"><title>事故数据时空质量复核</title><style>body{font-family:"Microsoft YaHei",sans-serif;max-width:1500px;margin:36px auto;background:#f3f6fa;color:#1c2d3d;padding:0 20px}h1{font-size:30px}section{background:white;padding:25px;margin:24px 0;border-radius:12px}img{width:100%;height:auto}p{line-height:1.8}a{color:#2468a4}strong{color:#163e68}</style>'
    html+=f'<h1>事故数据时空质量复核</h1><p>{t["jurisdictions"]}个辖区 · {t["annual_files"]}个年度文件 · {t["rows"]:,}条记录<br>有效坐标 {t["valid_coordinates"]/t["rows"]:.2%}；具体日期 {t["exact_date"]/t["rows"]:.2%}；有事故时刻 {t["time_available"]/t["rows"]:.2%}。</p>'
    html+='<p><strong>读图说明：</strong>这是已收集事故的分布，不是事故风险地图。各州年份、报告门槛和字段覆盖不同；2026是进行中年度。灰色缺失不能解释为零事故。FL 2020–2025现仅含CODEABLE=Y；MO 2024–2025明显低于官方年报快照，2026完整性未验证，不能当完整全州样本。</p><p><a href="spatiotemporal_quality_review.pdf">下载全部图件PDF</a> · <a href="review_flags.csv">复核清单CSV</a> · <a href="README.md">方法与发现</a></p>'
    for name,title in cards:html+=f'<section><h2>{title}</h2><a href="{name}.png"><img src="{name}.png" alt="{title}"></a></section>'
    (OUT/'index.html').write_text(html,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=3);parser.add_argument('--plots-only',action='store_true')
    args=parser.parse_args();OUT.mkdir(exist_ok=True,parents=True);(OUT/'cache').mkdir(exist_ok=True)
    states=sorted(p.name for p in (ROOT/'data/crash').iterdir() if p.is_dir() and len(p.name)==2)
    if args.plots_only:
        results=[json.loads((OUT/'cache'/f'{st}.json').read_text(encoding='utf-8')) for st in states]
    else:
        results=[]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(scan_state,st):st for st in states}
            for f in as_completed(futures):
                r=f.result();results.append(r);print(f'COMPLETE {r["state"]} {len(results)}/{len(states)}',flush=True)
    results.sort(key=lambda r:r['state'])
    a,s,frames,t=assemble(results);plot(a,s,frames,t);write_report(a,s,frames,t)
    print(json.dumps(t),flush=True)


if __name__=='__main__':main()
