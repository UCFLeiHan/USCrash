"""Variable-specific screening from existing QA; no crash records are modified.

Candidates pass metadata coverage thresholds, not external census verification.
Time labels and source populations still need review before confirmatory analysis.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
import pandas as pd

U=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')
Q=U/'qa/spatiotemporal_review_2026-10-14'
E=U/'qa/external_validation_2026-10-14/analysis_eligibility_511_state_years.csv'
O=U/'qa/analysis_readiness_2026-10-14'

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    O.mkdir(exist_ok=True)
    e=pd.read_csv(E);a=pd.read_csv(Q/'annual.csv');p=pd.read_csv(Q/'precision.csv')
    d=e.merge(a[['state','year','month_available','months_with_records','calendar_year_mismatch']],
              on=['state','year'],validate='one_to_one')
    # Conservative common comparison gate. Individual excluded years may still
    # support separately labeled subset or matched-YTD analyses.
    gate=~d.annual_total_status.str.startswith(('EXCLUDE','REVIEW'))
    d['population_coverage_gate']=gate
    d['season_candidate']=gate&(d.month_available/d.records>=.95)&d.months_with_records.eq(12)
    d['weekday_candidate']=gate&d.exact_date_rate.ge(.95)
    d['hour_candidate']=gate&d.time_available_rate.ge(.95)
    d['fine_kabco_candidate']=gate&d.fine_kabco_rate.ge(.95)
    d['c09_candidate']=gate&d.manner_known_rate.ge(.9)
    ranges=p[p.time_precision.eq('HOUR_RANGE')].groupby(['state','year']).rows.sum()
    d['hour_range_rows']=[int(ranges.get((r.state,r.year),0)) for r in d.itertuples()]
    d['hour_range_review_required']=d.hour_range_rows.gt(0)
    d['joint_field_rate_candidate']=d[['season_candidate','weekday_candidate','hour_candidate',
                                       'fine_kabco_candidate','c09_candidate']].all(axis=1)
    expected=json.loads((U/'qa/cross_state/final_42_state_integrity_audit.json').read_text())
    assert int(d.records.sum())==expected['total_harmonized_records']
    d.to_csv(O/'state_year_variable_readiness.csv',index=False,encoding='utf-8-sig')
    year=2023;z=d[d.year.eq(year)]
    stats=[]
    labels=[('季节','season_candidate'),('星期','weekday_candidate'),('小时/时段','hour_candidate'),
            ('细分KABCO','fine_kabco_candidate'),('C09碰撞形态','c09_candidate')]
    lines=['# 描述性分析准备情况','',
           '可以开展按变量选择样本的描述性分析；不能将全部州、全部年度直接合并并称为全美事故普查。',
           '本报告只复用现有QA，未修改原始或统一事故数据。门槛沿用既有分析清单：月份、日期、时间或细伤情覆盖至少95%；已知C09至少90%。已知不完整年度、子集以及待核实的来源切换不纳入共同年度总量比较。',
           '',f'## {year}年初筛（仅字段覆盖，不等于已完成外部验证）','',
           '|分析|候选辖区数|这些辖区的记录总数|','|---|---:|---:|']
    for label,col in labels:
        v=z[z[col]];n=int(v.records.sum());stats.append(dict(variable=label,jurisdictions=len(v),records_in_candidate_jurisdictions=n))
        lines.append(f'|{label}|{len(v)}|{n:,}|')
    lines+=['','上表记录总数不是最终有效观测数；正式绘图还要逐条去除该变量缺失值，并保留缺失率。',
            f'同年满足五项字段率门槛的辖区共{int(z.joint_field_rate_candidate.sum())}个：'+', '.join(z.loc[z.joint_field_rate_candidate,'state'])+'。仍需核对时间精度与报告口径，不应称为已通过全国外部校验。',
            '', '## 使用规则','',
            '- 季节使用有效月份及完整季节窗口；冬季DJF须明确跨年定义。部分年度与2026 YTD另表处理。',
            '- 星期从有效具体事故日期计算。PA、NM及OH部分年份缺日号，不能用月份补造星期；原始星期字段如要补入须另行验证。',
            '- 小时保留当地时钟。HOUR可用于小时分组；HOUR_RANGE先验证区间宽度，不能把区间起点解释成精确分钟。无时刻的记录单列。',
            '- 细伤情中U、缺失、未提供分别保留；已知笼统受伤不能强拆A/B/C。',
            '- C09未知99及空值不作为已知形态。首次有害事件和碰撞对象可另作分析，不能据此直接恢复所有C09几何形态。',
            '- MO 2024–2025低于官方年报快照，2026完整性未验证；暂不作完整全州总量样本。',
            '- 部分年度：AL2025、FL2019、ID2023、MA2001、MO2003、MS2019、TX2019；所有2026年为YTD。',
            '- OK为KAB伤害子集；NC2016–2020为KA子集。NC近期按已接受的公开表口径分析。',
            '- NV来源切换、ID2012–2013数量断层继续保留复核标志；NV空间坐标系尚待官方确认。',
            '- 当前C09已知覆盖为零的辖区：DC、ID、KS、MN、MO、MS、NE、OK、WA；这不等于所有事故类型信息都缺失。',
            '- AR、DE、ID存在少量归档年份与事故年份不一致记录；按实际事故日期归组，并检查跨年重复。',
            '- 缺坐标不自动影响以上五项非空间分析。图中比例以收集到的合格事故为分母，不能解释为暴露量校正后的风险。',
            '', '## 复现','', '`python scripts/build_analysis_readiness.py`；输入为现有annual.csv、precision.csv和州—年纳入清单，输出state_year_variable_readiness.csv。']
    (O/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    pd.DataFrame(stats).to_csv(O/'summary_2023.csv',index=False,encoding='utf-8-sig')
    meta=dict(generated_utc=datetime.now(timezone.utc).isoformat(),records=int(d.records.sum()),
              state_years=len(d),scope='METADATA_CANDIDATES_NOT_EXTERNAL_COMPLETENESS_CERTIFICATION',
              source_sha256={str(x.relative_to(U)):hashlib.sha256(x.read_bytes()).hexdigest()
                             for x in [E,Q/'annual.csv',Q/'precision.csv']})
    (O/'manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(pd.DataFrame(stats).to_string(index=False))
    print('Joint field-rate candidates:',int(z.joint_field_rate_candidate.sum()))

if __name__=='__main__':main()
