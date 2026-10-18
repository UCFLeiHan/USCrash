"""Freeze external comparison evidence and conservative analysis eligibility.

Reads preserved raw/canonical files. Never overwrites crash data. The separately
audited FL revision selects CODEABLE=Y in canonical 2017-2025 files and preserves
all exclusions in an ID ledger. State-year status is task-specific, not a claim
of census completeness. Official count snapshots may have different cutoffs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path

import pandas as pd

ROOT=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')
RAW=ROOT.parent/'States'
REVIEW=ROOT/'qa/spatiotemporal_review_2026-10-14'
OUT=ROOT/'qa/external_validation_2026-10-14'

URLS={
 'FL_2021_Crash_Facts.pdf':'https://www.flhsmv.gov/pdf/crashreports/crash_facts_2021_ada.pdf',
 'FL_2023_Crash_Facts.pdf':'https://www.flhsmv.gov/pdf/crashreports/crash_facts_2023.pdf',
 'FL_Signal4_Data_Dictionary.pdf':'https://signal4analytics.com/assets/files/S4_Data_Dictionary.pdf',
 'MO_2023_Annual_Report.pdf':'https://apps.mshp.dps.mo.gov/MSHPWeb/Publications/OtherPublications/documents/2023AnnualReport.pdf',
 'MO_2024_Annual_Report.pdf':'https://apps.mshp.dps.mo.gov/MSHPWeb/Publications/OtherPublications/documents/2024AnnualReport.pdf',
 'MO_2025_Annual_Report.pdf':'https://www.mshp.dps.mo.gov/MSHPWeb/Publications/OtherPublications/documents/2025AnnualReport.pdf',
 'NC_2023_Crash_Facts.pdf':'https://connect.ncdot.gov/business/DMV/CrashFactsDocuments/2023%20Crash%20Facts.pdf',
 'NC_2024_Crash_Facts.pdf':'https://connect.ncdot.gov/business/DMV/CrashFactsDocuments/2024%20Crash%20Facts.pdf',
}


def write_json(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def evidence_refs():
    """Structured transcription, checked against the exact PDF page text."""
    refs=[]
    def add(st,yr,number,file,page,anchor,scope):
        assert (OUT/'reference'/file).exists(),file
        refs.append(dict(state=st,year=yr,official_crashes=number,reference_file=file,
                         pdf_page=page,printed_page={'FL_2021_Crash_Facts.pdf':'',
                         'FL_2023_Crash_Facts.pdf':'8','MO_2023_Annual_Report.pdf':'45',
                         'MO_2024_Annual_Report.pdf':'43','MO_2025_Annual_Report.pdf':'45','NC_2024_Crash_Facts.pdf':'4'}.get(file,''),
                         reference_url=URLS[file],reference_scope=scope,text_anchor=anchor))
    for yr,n in [(2019,401867),(2020,341399),(2021,401540)]:
        add('FL',yr,n,'FL_2021_Crash_Facts.pdf',9,'Total Codeable Crashes','CODEABLE crashes in published Crash Facts snapshot')
    for yr,n in [(2022,397620),(2023,395175)]:
        add('FL',yr,n,'FL_2023_Crash_Facts.pdf',9,'Total Codable Crashes','CODABLE crashes in published Crash Facts snapshot')
    add('MO',2023,136516,'MO_2023_Annual_Report.pdf',45,'136,516','Motor vehicle traffic crashes reported to Patrol Records Division, 2023 annual snapshot')
    add('MO',2024,103960,'MO_2024_Annual_Report.pdf',45,'103,960','Motor vehicle traffic crashes reported to Patrol Records Division, 2024 annual snapshot')
    add('MO',2025,105195,'MO_2025_Annual_Report.pdf',47,'105,195','Motor vehicle traffic crashes reported to Patrol Records Division, 2025 annual snapshot; preliminary')
    for yr,n in [(2021,276026),(2022,273732),(2023,284157),(2024,284546)]:
        add('NC',yr,n,'NC_2024_Crash_Facts.pdf',8,'Total Crashes','Reportable traffic crashes, 2024 Crash Facts comparison table')
    # Ensure transcription anchors and count tokens exist on the claimed pages.
    from pypdf import PdfReader
    readers={}
    for r in refs:
        if r['reference_file'] not in readers:readers[r['reference_file']]=PdfReader(str(OUT/'reference'/r['reference_file']))
        text=readers[r['reference_file']].pages[r['pdf_page']-1].extract_text() or ''
        assert f'{r["official_crashes"]:,}' in text, r
        assert r['text_anchor'].lower() in text.lower(),r
        r['reference_page_marks_preliminary']='preliminary' in text.lower()
    df=pd.DataFrame(refs);df.to_csv(OUT/'official_reference_counts.csv',index=False,encoding='utf-8-sig')
    return df


def raw_scope_audits():
    result=[]
    for y in range(2017,2026):
        p=RAW/'FL'/str(y)/'CSV'/f'FL_Signal4_crashes_{y}.csv'
        cols=['REPORT_NUMBER','CODEABLE','FORM_TYPE','COMPLETED_FLAG','S4_FATALITY_WITHIN_30_DAYS_COUNT']
        d=pd.read_csv(p,usecols=cols,dtype=str,keep_default_na=False)
        assert d.REPORT_NUMBER.is_unique,(y,'source report ID not unique')
        by_code=d.CODEABLE.value_counts().to_dict()
        assert set(by_code)<= {'Y','N'},(y,by_code)
        r=dict(state='FL',year=y,raw_rows=len(d),unique_reports=int(d.REPORT_NUMBER.nunique()),
               codeable_y=int(by_code.get('Y',0)),codeable_n=int(by_code.get('N',0)),
               form_long=int(d.FORM_TYPE.eq('L').sum()),form_short=int(d.FORM_TYPE.eq('S').sum()),
               completed_yes=int(d.COMPLETED_FLAG.eq('Y').sum()),source_file=str(p))
        result.append(r)
    fl=pd.DataFrame(result);fl.to_csv(OUT/'FL_raw_scope_counts.csv',index=False,encoding='utf-8-sig')
    nc=[];mo=[]
    for y in range(2021,2027):
        p=RAW/'NC'/str(y)/'NCDOT_public_crash_table.csv'
        d=pd.read_csv(p,usecols=['Crash_ID','CrshSeverity','NumFatalities'],dtype=str,keep_default_na=False)
        nc.append(dict(state='NC',year=y,raw_rows=len(d),unique_reports=int(d.Crash_ID.nunique()),
                       fatalities=int(pd.to_numeric(d.NumFatalities,errors='coerce').sum()),
                       severity_counts=d.CrshSeverity.value_counts().to_dict()))
    for y in [2023,2024,2025,2026]:
        p=RAW/'MO'/str(y)/f'MO_crashes_{y}.csv'
        d=pd.read_csv(p,usecols=['ACCIDENT','KILLED','SEVERITY','AGENCY','ACC_DATE'],dtype=str,keep_default_na=False)
        mo.append(dict(state='MO',year=y,raw_rows=len(d),unique_reports=int(d.ACCIDENT.nunique()),
                       fatalities=int(pd.to_numeric(d.KILLED,errors='coerce').sum()),
                       agency_count=int(d.AGENCY.nunique()),severity_counts=d.SEVERITY.value_counts().to_dict()))
    write_json(OUT/'NC_raw_scope_audit.json',nc);write_json(OUT/'MO_raw_scope_audit.json',mo)
    return fl,nc,mo


def compare(refs,fl,annual):
    totals=annual.set_index(['state','year']).rows
    rows=[]
    for _,r in refs.iterrows():
        st,y=r.state,int(r.year);all_count=int(totals[st,y])
        view='ALL_LOCAL_RECORDS';comparison=all_count
        reason='Unresolved population, cutoff or definition difference; no count adjustment applied.'
        if st=='FL' and y>=2017:
            comparison=int(fl.loc[fl.year.eq(y),'codeable_y'].iloc[0]);view='RAW_CODEABLE_EQUALS_Y'
            assert all_count==comparison,(y,'Canonical FL must already use CODEABLE=Y')
            reason='Canonical table was rebuilt using raw CODEABLE=Y. Original all-report table and excluded ID ledger preserved. Residual difference is not explained or force-adjusted.'
        delta=comparison-int(r.official_crashes);ratio=delta/int(r.official_crashes)
        status='WITHIN_1PCT_SCREEN_NOT_IDENTITY_VERIFIED' if abs(ratio)<=.01 else 'MATERIAL_DIFFERENCE_REVIEW_REQUIRED'
        if st=='MO' and y>=2024:reason='Public layer and local extract are both much smaller than the annual-report snapshot; tiny new live-layer increments do not explain the deficit. Reports are preliminary. MUCR transition is documented, but causation of the gap remains unconfirmed.'
        if st=='NC':
            status='PUBLIC_TABLE_SCOPE_ACCEPTED_NO_ROW_CHANGES'
            reason='User accepts using the public-table population; do not trim or investigate further here. Its total is not the published reportable-crash total. Do not label the difference duplicates or private-road crashes without evidence.'
        raw_all=int(fl.loc[fl.year.eq(y),'raw_rows'].iloc[0]) if st=='FL' and y>=2017 else all_count
        rows.append(dict(**r.to_dict(),local_all_records=all_count,raw_all_reports=raw_all,comparison_view=view,
                         comparison_records=comparison,delta=delta,relative_difference=ratio,status=status,explanation=reason))
    df=pd.DataFrame(rows);df.to_csv(OUT/'benchmark_totals.csv',index=False,encoding='utf-8-sig');return df


def semantic_screen():
    flags=[]
    for p in sorted((ROOT/'config/states').glob('*.json')):
        j=json.loads(p.read_text(encoding='utf-8-sig'))
        for v in j.get('versions',[]):
            field=v.get('fields',{}).get('first_harmful_event_raw_code','')
            if 'MOST_HARM' in field.upper():
                flags.append(dict(state=j['state'],year_start=v['year_start'],year_end=v['year_end'],
                    canonical_field='first_harmful_event',source_field=field,status='DO_NOT_USE_PENDING_SEMANTIC_REVIEW',
                    reason='MOST harmful event and FIRST harmful event are different concepts. Existing mapping is not accepted for analysis based solely on compatible category labels.'))
    pd.DataFrame(flags,columns=['state','year_start','year_end','canonical_field','source_field','status','reason']).to_csv(OUT/'semantic_review_flags.csv',index=False,encoding='utf-8-sig')
    return flags


def eligibility(annual,bench,semantic):
    rows=[];bench_index={(r.state,int(r.year)):r for r in bench.itertuples()}
    partial={('AL',2025),('ID',2023),('MA',2001),('MO',2003),('MS',2019),('TX',2019)}
    for _,r in annual.iterrows():
        st,y,n=r.state,int(r.year),int(r.rows)
        reason=[];status='CANDIDATE_INTERNAL_ONLY';scope='SOURCE_DEFINED_NOT_EXTERNALLY_AUDITED'
        selection='';evidence='NOT_AUDITED'
        if st=='OK':scope='KAB_INJURY_SUBSET';status='EXCLUDE_FROM_ALL_SEVERITY_TOTALS';reason.append('Not all-severity crash universe')
        if st=='NC' and y<=2020:scope='KA_SUBSET';status='EXCLUDE_FROM_ALL_SEVERITY_TOTALS';reason.append('K/A subset cannot be pooled with 2021+ full public table')
        if st=='NC' and y>=2021:scope='PUBLIC_TABLE_POPULATION_USER_ACCEPTED';status='CANDIDATE_WITH_PUBLIC_TABLE_SCOPE';reason.append('Scope accepted; retained as supplied. Public-table total is distinct from published reportable count')
        if st=='MO' and y in [2024,2025]:
            scope='PUBLIC_MAP_LAYER_INCOMPLETE_AGAINST_ANNUAL_SNAPSHOT';status='EXCLUDE_PENDING_SOURCE_COVERAGE_REVIEW'
            reason.append('Public map layer has substantially lower counts than the same-year preliminary annual report')
        if st=='MO' and y>=2026:
            scope='PUBLIC_MAP_LAYER_YTD_COMPLETENESS_UNVERIFIED';status='EXCLUDE_PENDING_SOURCE_COVERAGE_REVIEW'
            reason.append('Same source as deficient 2024/2025; no independent same-cutoff total verifies current YTD completeness')
        if st=='NV':status='REVIEW_SOURCE_SWITCH_BEFORE_TOTAL_COMPARISON';reason.append('2019 ArcGIS and 2020+ request extract are different products; coverage continuity not externally confirmed')
        if st=='ID' and y in [2012,2013]:status='REVIEW_COUNT_DISCONTINUITY';reason.append('2012 count drop and 2013 rebound require official annual total comparison')
        if st=='FL' and y<2017:
            scope='FDOT_SOURCE_DEFINED_NO_CODEABLE_FLAG'
            reason.append('Legacy FDOT inputs do not expose the reviewed Signal4 CODEABLE filter; identical populations across the source switch are not established')
        if st=='FL' and y>=2017:
            scope='CODEABLE_Y_ALREADY_SELECTED';selection='Already filtered using raw REPORT_NUMBER / CODEABLE=Y; do not append excluded N reports'
            status='CANDIDATE_CODEABLE_POPULATION';reason.append('All-report source retained separately; residual annual-report differences remain')
        if st=='FL' and 2011<=y<=2016:reason.append('Most-event mapping removed. First event is unavailable; most-event observations retained in revision sidecar')
        b=bench_index.get((st,y))
        if b:
            evidence=b.status
            if b.status=='WITHIN_1PCT_SCREEN_NOT_IDENTITY_VERIFIED' and status=='CANDIDATE_INTERNAL_ONLY':status='CANDIDATE_EXTERNAL_AGGREGATE_SCREENED'
        if (st,y) in partial:status='EXCLUDE_PARTIAL_OR_INCOMPLETE_YEAR';reason.append('Known or empirically observed incomplete annual window')
        if y==2026:status='EXCLUDE_YTD_FROM_ANNUAL_TOTALS';reason.append('Calendar 2026 is in progress')
        # Task-specific field gates are screening thresholds, not proof of complete capture.
        coord=float(r.valid_coordinates)/n;day=float(r.exact_date)/n
        severity=float(r.severity_specific_kabco)/n;manner=float(r.manner_known)/n
        spatial='CANDIDATE_RECORD_FILTER_REQUIRED' if coord>=.95 else ('CONDITIONAL_HIGH_MISSINGNESS' if coord>=.8 else 'EXCLUDE_FROM_COMPARABLE_SPATIAL_DENSITY')
        if st in {'NV','MT'}:
            crs_review=ROOT/'qa/coordinate_revision_2026-10-14/crs_review.json'
            reviewed=json.loads(crs_review.read_text()).get(st,{}) if crs_review.exists() else {}
            if reviewed.get('status')=='OFFICIAL_CRS_AND_LOCATION_CHECKED':
                reason.append('Projected XY converted using '+reviewed['source_crs']+'; official GIS metadata, hosted sample points and independent county/state screens checked; positional accuracy is not guaranteed')
            elif st=='NV':
                spatial='HOLD_UNCONFIRMED_SOURCE_CRS';reason.append('Projected source CRS has not passed the documented review')
        if r.polygon_outside_2km>0:reason.append('Exclude/inspect polygon-outside-2km records using independent screen; flag is not a correction')
        daily='CANDIDATE' if day>=.95 else 'EXCLUDE_FROM_DAY_LEVEL_ANALYSIS'
        injury='CANDIDATE_COMPLETE_CASES_ONLY' if severity>=.95 else ('CONDITIONAL_LABEL_MISSINGNESS' if severity>=.8 else 'EXCLUDE_FROM_FINE_KABCO_COMPARISON')
        collision='CANDIDATE_KNOWN_CODES_ONLY' if manner>=.9 else 'CONDITIONAL_MISSING_OR_UNKNOWN_MANNER'
        blocked=any(x['state']==st and x['year_start']<=y<=x['year_end'] for x in semantic)
        first='HOLD_SEMANTIC_MAPPING' if blocked else ('AVAILABLE_FIELD_REVIEW_REQUIRED' if r.fhe_known>0 else 'UNAVAILABLE')
        rows.append(dict(state=st,year=y,records=n,annual_total_status=status,source_scope=scope,
            external_validation=evidence,required_selection=selection,spatial_status=spatial,
            valid_coordinate_rate=coord,polygon_outside_2km=int(r.polygon_outside_2km),
            day_level_status=daily,exact_date_rate=day,time_available_rate=float(r.time_available)/n,
            fine_kabco_status=injury,fine_kabco_rate=severity,manner_status=collision,manner_known_rate=manner,
            first_harmful_event_status=first,first_date=r.first_date if pd.notna(r.first_date) else '',
            last_date=r.last_date if pd.notna(r.last_date) else '',notes='; '.join(reason)))
    e=pd.DataFrame(rows)
    assert len(e)==511 and not e.duplicated(['state','year']).any()
    current=json.loads((ROOT/'qa/cross_state/final_42_state_integrity_audit.json').read_text())
    assert e.records.sum()==current['total_harmonized_records']
    e.to_csv(OUT/'analysis_eligibility_511_state_years.csv',index=False,encoding='utf-8-sig')
    rules=dict(version='0.1',scope='Provisional screening; not a national completeness certification',
       spatial_default_minimum_coordinate_rate=.95,spatial_conditional_minimum=.8,
       day_level_minimum_exact_date_rate=.95,fine_kabco_default_minimum=.95,
       manner_default_minimum_known_rate=.9,external_count_screen_tolerance=.01,
       forbidden_inferences=['Do not equate count agreement with record-level validation',
         'Do not interpret missing months or coordinates as zero crashes',
         'Do not infer excess NC rows are non-reportable without a definition',
         'Do not assume the MO gap is caused by MUCR transition',
         'Do not call most harmful event the first harmful event'],
       thresholds_note='Thresholds are transparent analysis choices; conduct sensitivity analysis. All universes and severity definitions still require review.',
       status_counts=e.annual_total_status.value_counts().to_dict())
    write_json(OUT/'analysis_rules.json',rules)
    return e,rules


def plot(bench):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,
                        'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,3,figsize=(20,7))
    for ax,st in zip(axs,['FL','MO','NC']):
        d=bench[(bench.state==st)&(bench.year>=2020)].sort_values('year');x=np.arange(len(d));w=.25
        ax.bar(x-w,d.raw_all_reports/1000,w,color='#9ba8b6',label='原始全部报告' if st=='FL' else '本地记录')
        if st=='FL':ax.bar(x,d.comparison_records/1000,w,color='#276b9b',label='本地CODEABLE=Y')
        ax.bar(x+w,d.official_crashes/1000,w,color='#d3943c',label='官方年报口径')
        ax.set_xticks(x,d.year.astype(int));ax.set_ylabel('记录数（千）');ax.set_title(st,loc='left',fontweight='bold')
        ax.set_ylim(0,max(d.raw_all_reports.max(),d.official_crashes.max())/1000*1.24)
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);ax.legend(frameon=False,fontsize=9)
    fig.suptitle('外部核对：相同州年度并不自动意味着相同统计范围',fontsize=21,y=.99)
    fig.text(.045,.045,'FL：统一表已选择CODEABLE=Y；MO：2024及2025公开图层均明显低于年报；NC：保留公开表口径。',fontsize=11)
    fig.text(.045,.012,'参考数采用冻结的官方报告版本，非实时最终真值。1%仅为差异筛查阈值；不代表逐条匹配、完整性证明或精确相等。',fontsize=10,color='#55616e')
    fig.subplots_adjust(top=.87,bottom=.17,wspace=.3)
    fig.savefig(OUT/'external_count_comparison.png',dpi=190,bbox_inches='tight');plt.close(fig)


def report(bench,e,rules):
    revision=ROOT/'qa/revisions/2026-10-14_FL_codeable_fhe'
    manifest=json.loads((revision/'promotion_manifest.json').read_text())
    fl_validation=json.loads((ROOT/'qa/post_harmonization/FL/validation_report.json').read_text())
    total=int(e.records.sum())
    lines=['# 外部核对与分析纳入清单（已更新FL修正与MO近期覆盖审查）','',
      f'当前统一表：42个辖区、511个年度CSV、{total:,}条记录。内部完整性PASS不等于各州完整事故普查。',
      '', '## 已执行的修正',
      f'- FL 2020–2025按原始CODEABLE=Y重新生成正式统一表；共排除{manifest["excluded_codeable_n"]:,}条CODEABLE=N报告。N不等于错误或重复，属于本次研究口径之外。原始数据、被排除ID清单和旧版输出均保留。',
      '- FL 2023统一表为393,241条，对应原始CODEABLE=Y。官方2023 Crash Facts为395,175条，仍相差1,934条（−0.49%）。目前没有逐条证据解释差额，不补造或按总量删改记录。',
      '- FL 2011–2019已移除MOST_HARM_EVNT_CD到first_harmful_event的错误映射，同时清空依赖它的first_harmful_event_group和collision_partner_group。首次事件标记UNAVAILABLE；事故形态C09、天气、时间、坐标、伤情等逐格核对保持一致。',
      '- FRST_HARM_LOC_CD是事件位置，不是事件类型；不能替代缺失的首次事件。原MOST事件观察值保存在修正目录的压缩CSV旁表，原始文件不变。',
      '- NC按用户决定保留公开表范围，未筛删、未重跑NC文件；与reportable总量的差别仅作为口径说明，不据此判为重复或无效。',
      '', '## MO：2024之后是否都有问题',
      '- 2024：本地59,769条，当前公开图层也是59,769条；官方2024年报为103,960条，本地少42.51%。',
      '- 2025：本地34,332条，当前公开图层34,333条；官方2025年报为105,195条，本地少67.36%。只重新下载同一图层不能补齐大缺口。',
      '- 两年均有12个月及115个县级辖区的记录；月份/地区出现不代表完整覆盖。不是简单漏下载一个季度，也不能断言新版MUCR是缺口原因。',
      '- 2026：本地20,725条，日期截至10月5日；当前同一公开图层21,109条。全年尚未结束，未取得同截止日全州总量，不能量化漏报比例；标记YTD且完整性未验证，暂停作为全州完整样本。',
      '- MO 2024和2025官方年报均为preliminary快照，仍在处理，比较比例针对明确保存的报告版本；不能视为最终普查真值。2025年报“较上年少1,235”隐含2024回溯值106,430，与2024报告的103,960不同；保留版本差异，不混用。',
      '- 官方披露2024启用新版MUCR；时间一致仅提示应调查来源衔接，不能证明因果。2023公开图层与当年年报相差+0.45%。',
      '', '## 官方数量比较（未为配平而修改记录）',
      '|州|年度|正式统一表|比较条数|官方年报快照|差异|','|---|---:|---:|---:|---:|---:|']
    for r in bench.itertuples():
        lines.append(f'|{r.state}|{r.year}|{r.local_all_records:,}|{r.comparison_records:,}|{r.official_crashes:,}|{r.relative_difference:+.2%}|')
    lines+=['','## 511个州—年份的分析条件','',
      'MO 2024及以后保留已有记录，但暂停完整全州总量比较。所有2026年数据仅为YTD。NC继续按公开表口径使用；早期K/A子集与后续公开表仍须分开。',
      '字段率筛查、内部一致性校验和外部完整性是不同的检查，任何一项PASS都不替代其他检查。',
      '|年度总量状态|州年数|','|---|---:|']
    for k,v in rules['status_counts'].items():lines.append(f'|{k}|{v}|')
    lines+=['','## 可复现文件','',
      '- official_reference_counts.csv：官方PDF、URL、精确页码、数值与版本。',
      '- benchmark_totals.csv：正式表、原始报告数、可比较范围与差额。',
      '- MO_2023_2026_coverage_audit.csv：逐年本地/在线/年报对照、日期、县与机构数量。',
      '- MO_recent_monthly_counts.csv、MO_recent_agency_counts.csv：近期覆盖分布。',
      '- analysis_eligibility_511_state_years.csv：年度总量、空间、日级、KABCO、形态及FHE分别判断。',
      '- reference/：报告原文、PDF提取文本与在线图层快照；reference_download_manifest.json记录SHA-256。',
      '- ../revisions/2026-10-14_FL_codeable_fhe/：逐条修正审计、被排除ID、MOST事件旁表、旧文件和promotion_manifest.json。',
      '- 完整原始重建：使用修正后的config/states/FL.json运行python scripts/harmonize_crash.py --state FL，再运行validate_harmonized_crash.py --state FL。逐条修正验证脚本为scripts/verify_promote_fl_revision.py。',
      '- CODEABLE筛选只适用于有该官方标志的2020–2025；不能声称旧FDOT年份已经过相同筛选。',
      '', '## 剩余限制','',
      '- FL 2023的1,934条差额保留为未解释残差；需要官方同版本逐条或更细分统计佐证。',
      '- MO需另找完整近期来源或向官方申请；保留现有子集，不补造缺失事故。',
      f'- FL独立校验保留的源字段一致性提示为{fl_validation["issues"]}；PASS不表示这些提示已经消失，不能仅凭提示判为无效事故或强行改写源值。',
      '- 其他州未在本轮接受外部总量普查核验；既有缺坐标、缺日期或不完整年度限制继续保留。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>外部核对与分析纳入</title><style>body{font-family:"Microsoft YaHei",sans-serif;max-width:1400px;margin:36px auto;color:#203346;padding:20px}p{line-height:1.8}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #dce2e9;text-align:right}td:first-child,th:first-child{text-align:left}img{width:100%}a{color:#21639a}</style><h1>外部核对与分析纳入清单</h1>'
    page+=f'<p>当前统一数据：42个辖区 · 511个年度CSV · {total:,}条记录。FL修正已生效，原始文件保留。</p>'
    page+='<p><strong>FL：</strong>2020–2025统一表已按CODEABLE=Y筛选；2023与年报仍差1,934条（−0.49%），未为配平删改记录。2011–2019误接的首次有害事件字段已清空，MOST事件保留在旁表。</p>'
    page+='<p><strong>MO：</strong>2024比年报少42.51%，2025少67.36%；2026为YTD且完整性未验证。近期记录保留，但暂停完整全州总量分析。<strong>NC：</strong>按用户决定保持公开表口径与原记录。</p>'
    page+='<img src="external_count_comparison.png" alt="外部数量对比"><p><a href="analysis_eligibility_511_state_years.csv">511州年分析清单</a> · <a href="MO_2023_2026_coverage_audit.csv">MO近期覆盖审查</a> · <a href="README.md">完整方法与限制</a> · <a href="../revisions/2026-10-14_FL_codeable_fhe/record_level_revision_audit.csv">FL逐条修正审计</a></p>'
    cols=['state','year','local_all_records','raw_all_reports','comparison_records','official_crashes','relative_difference']
    x=bench[cols].copy();x.relative_difference=x.relative_difference.map(lambda v:f'{v:+.2%}');page+=x.to_html(index=False)
    (OUT/'index.html').write_text(page,encoding='utf-8')


def export_fl(year):
    """Non-destructive comparable view, retaining all 77 canonical columns."""
    if not 2017<=year<=2025:raise ValueError('Only reviewed Signal4 2017–2025 CODEABLE flag is supported')
    raw=RAW/'FL'/str(year)/'CSV'/f'FL_Signal4_crashes_{year}.csv'
    flags=pd.read_csv(raw,usecols=['REPORT_NUMBER','CODEABLE'],dtype=str,keep_default_na=False)
    assert flags.REPORT_NUMBER.is_unique
    allowed=set(flags.loc[flags.CODEABLE.eq('Y'),'REPORT_NUMBER'])
    source=ROOT/'data/crash/FL'/f'FL_crashes_harmonized_{year}.csv'
    folder=ROOT/'analysis_views/FL_CODEABLE_Y';folder.mkdir(parents=True,exist_ok=True)
    dest=folder/f'FL_codeable_y_{year}.csv';partial=dest.with_suffix('.csv.partial');written=0;first=True
    for d in pd.read_csv(source,dtype=str,keep_default_na=False,chunksize=150000):
        selected=d[d.source_crash_id.isin(allowed)]
        selected.to_csv(partial,index=False,mode='w' if first else 'a',header=first,encoding='utf-8')
        written+=len(selected);first=False
    assert written==len(allowed),(written,len(allowed))
    partial.replace(dest)
    write_json(folder/f'FL_codeable_y_{year}.manifest.json',dict(year=year,records=written,
       source=str(source),raw_flags=str(raw),selection='RAW.CODEABLE == Y on source_crash_id == REPORT_NUMBER',
       official_comparison_not_exact=True,columns=77,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    print('EXPORTED',dest,written,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--export-fl',type=int,nargs='*');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.export_fl:
        for y in args.export_fl:export_fl(y)
        return
    annual=pd.read_csv(REVIEW/'annual.csv')
    refs=evidence_refs();fl,nc,mo=raw_scope_audits();bench=compare(refs,fl,annual)
    sem=semantic_screen();e,rules=eligibility(annual,bench,sem)
    plot(bench);report(bench,e,rules)
    write_json(OUT/'audit_manifest.json',dict(generated_utc=datetime.now(timezone.utc).isoformat(),
       jurisdictions=42,state_years=len(e),records_preserved=int(e.records.sum()),
       this_audit_modifies_canonical_data=False,canonical_revision='2026-10-14_FL_codeable_fhe',benchmarked_states=['FL','MO','NC'],comparisons=len(bench),
       script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),thresholds=rules))
    print(bench[['state','year','local_all_records','comparison_records','official_crashes','relative_difference']].to_string(index=False),flush=True)
    print(e.annual_total_status.value_counts().to_string(),flush=True)


if __name__=='__main__':main()
