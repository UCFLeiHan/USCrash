"""Final archive audit after download processes finish; no source-data cleaning."""
import download_us_crashes as d
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,csv,re,shutil

plan_names=['download_plan.json','supplement_plan.json','dc_plan.json','denver_official_plan.json','fars_plan.json','pa_plan.json']
source_names=['sources.json','supplement_sources.json','dc_sources.json','denver_official_sources.json','fars_sources.json','pa_sources.json']
plan_names+=sorted(p.name for p in d.MANIFEST.glob('expansion*_plan.json'))
source_names+=sorted(p.name for p in d.MANIFEST.glob('expansion*_sources.json'))
plans=[];sources=[]
for name in plan_names:
    p=d.MANIFEST/name
    if p.exists():plans.extend(json.loads(p.read_text(encoding='utf-8')))
for name in source_names:
    p=d.MANIFEST/name
    if p.exists():sources.extend(json.loads(p.read_text(encoding='utf-8')))
source_groups={}
for source in sources:
    key=(source['region'],source['name']);source_groups.setdefault(key,[]).append(source)
sources=[]
for group in source_groups.values():
    merged=dict(group[0]);merged['years']=sorted({y for source in group for y in source.get('years',[]) if isinstance(y,int)})
    merged['urls']=sorted({source['url'] for source in group if source.get('url')})
    merged['source_records']=group;sources.append(merged)
jobs=list({j['id']:j for j in plans}.values())
inventory=[]
for p in d.ROOT.glob('*/*/*.metadata.json'):
    record=json.loads(p.read_text(encoding='utf-8'));record['receipt']=d.relative(p);inventory.append(record)

def audit(record):
    if record.get('status')!='complete':return {'path':record.get('path'),'status':'not_complete'}
    path=d.ROOT/record['path']
    if not path.resolve().is_relative_to(d.ROOT.resolve()):raise RuntimeError('Archive path escapes root')
    issues=[]
    if not path.exists():issues.append('missing file')
    else:
        if path.stat().st_size!=record.get('stored_bytes'):issues.append('byte length mismatch')
        if d.hash_file(path)!=record.get('sha256'):issues.append('SHA256 mismatch')
    expected=record.get('expected_records_snapshot')
    if expected is not None and record.get('records')!=expected:issues.append('snapshot row-count mismatch')
    if record.get('nonstandard_width_rows',0):issues.append('raw CSV contains nonstandard row widths: '+str(record['nonstandard_width_rows']))
    return {'path':record.get('path'),'status':'passed' if not issues else 'issues','issues':issues,
            'records':record.get('records'),'stored_bytes':record.get('stored_bytes')}

with ThreadPoolExecutor(4) as pool:checks=list(pool.map(audit,inventory))
d.atomic_json(d.MANIFEST/'integrity_audit.json',{'access_date':d.CLIENT_DATE,'checked_utc':d.stamp(),'files':checks,
              'passed':sum(x['status']=='passed' for x in checks),'issues':[x for x in checks if x['status']=='issues']})
lookup={r.get('path'):r for r in inventory}
job_status=[]
prior_status={}
for status_name in ['job_status.json','supplement_status.json','dc_status.json','denver_official_status.json','fars_status.json','pa_status.json']+sorted(p.name for p in d.MANIFEST.glob('expansion*_status.json')):
    status_path=d.MANIFEST/status_name
    if status_path.exists():
        for prior in json.loads(status_path.read_text(encoding='utf-8')):prior_status[prior['id']]=prior
for job in jobs:
    path=d.output_path(job);record=lookup.get(d.relative(path))
    if record:
        status=record.get('status');rows=record.get('records')
    elif prior_status.get(job['id'],{}).get('status')=='empty' and prior_status[job['id']].get('records')==0:
        status='empty';rows=0
    else:
        # Empty ArcGIS year slices have no dataset file. Confirm emptiness against the published source.
        if job['kind']=='arcgis':
            try:
                data=d.api(job['url']+'/query',{'where':job['where'],'returnCountOnly':'true','f':'json'},post=True)
                rows=data.get('count');status='empty' if rows==0 else 'missing'
            except Exception as exc:status='unverified';rows=None
        else:status='missing';rows=None
    job_status.append({'id':job['id'],'region':job['region'],'year':job.get('year'),'name':job['name'],
                       'status':status,'records':rows,'path':d.relative(path),'url':job['url']})
d.atomic_json(d.MANIFEST/'all_sources.json',sources)
d.atomic_json(d.MANIFEST/'all_job_status.json',job_status)
d.atomic_json(d.MANIFEST/'all_files.json',[{k:v for k,v in r.items() if k not in ['meta','fields']} for r in inventory])
complete=[r for r in inventory if r.get('status')=='complete']
groups={}
for record in complete:
    g=groups.setdefault(record['region'],{'years':set(),'files':0,'bytes':0})
    g['files']+=1;g['bytes']+=record.get('stored_bytes',0)
    if isinstance(record.get('year'),int):g['years'].add(record['year'])
summary={region:{**g,'years':sorted(g['years'])} for region,g in groups.items()}
d.atomic_json(d.MANIFEST/'summary.json',summary)
with (d.MANIFEST/'download_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
    keys=['region','year','name','status','records','stored_bytes','path','url','sha256','source_original','notes','error']
    writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
    for r in inventory:writer.writerow({k:r.get(k,'') for k in keys})

blocked=[{'region':'TX','reason':'CRIS public bulk extract requires registration/request; public query page returned 403 to this client.'},
         {'region':'NV','reason':'Identified official statewide service returned 500: not started.'},
         {'region':'MD','reason':'Identified old statewide public endpoint returned 403/login; newer download page not recovered.'}]
d.atomic_json(d.MANIFEST/'unavailable_sources.json',blocked)
for item in blocked:
    folder=d.ROOT/item['region'];folder.mkdir(exist_ok=True)
    (folder/'DOWNLOAD_STATUS.md').write_text('# 尚未取得数据\n\n'+item['reason']+'\n\n没有为该源创建空的年度数据文件。\n',encoding='utf-8')

# Remove only empty year directories created by zero-result slices, never recursively.
removed=[]
for folder in d.ROOT.glob('*/*'):
    if folder.is_dir() and re.fullmatch(r'(?:19|20)\d{2}',folder.name) and not any(folder.iterdir()):
        if not folder.resolve().is_relative_to(d.ROOT.resolve()):raise RuntimeError('Unexpected directory')
        folder.rmdir();removed.append(d.relative(folder))
d.atomic_json(d.MANIFEST/'removed_empty_year_directories.json',removed)

readme='# US公开事故数据归档\n\n下载访问日期：2026-10-08—2026-10-09（America/New_York）；各次获取UTC时间见单文件metadata.json。\n\n'
readme+='数据结构：`US/州缩写或城市名/年份/数据文件`。全国死亡事故补充包单列`FARS_Nationwide/年份`。原始多年Excel放在`MT/_source`，对应年度表按原始Crash Date拆分（保留Crash ID用于关联）。`_undated`为日期缺失/占位/无法确认的例外，不当作真实年份。\n\n'
readme+='CSV保存为`.csv.gz`，可直接用pandas.read_csv读取。ZIP和XLSX保留原始格式。原始年度CSV仅做gzip压缩，内容不改，年份沿用发布者的年度文件标签；ArcGIS导出保留公开属性并追加WGS84几何，日期数值通常仍是毫秒时间戳；Socrata导出保留业务字段，不含平台自动生成的computed_region字段。全部字段字典在`docs/source_metadata`。\n\n'
readme+='| 来源目录 | 实际有文件的年份 | 数据文件数 | 存储MB |\n|---|---|---:|---:|\n'
for region,g in sorted(summary.items()):
    years=g['years'];year_text=', '.join(map(str,years))
    readme+=f"| {region} | {year_text} | {g['files']} | {g['bytes']/1024**2:.1f} |\n"
readme+='\n## 覆盖与使用限制\n\n'
readme+='- 2026为当前不完整年份。门户实际保留日期可能比介绍更长；极少早期/占位日期保留不代表全年覆盖，例如1900年。\n'
readme+='- California最高伤害等级需关联人员表。Chicago在2017年9月以前覆盖有限，并通常不含非CPD响应高速事故。\n'
readme+='- Massachusetts历史查询层与年度Crash/Vehicle/Person表有重叠；Oregon原始GDB ZIP与OTSDE年度CSV也有重叠。不要把它们相加当独立事故。\n'
readme+='- MT年度CSV是原始Excel的分年副本，坐标为投影米；原文件也保留。\n'
readme+='- SF只含伤亡且排除高速；Cincinnati坐标有街区内扰动；DE类别较粗，2021年报告门槛变更。\n'
readme+='- NewYorkCity、OH、WashingtonDC、PA及Denver等为补充归档，部分缺失完整日期、标准碰撞类型或完整伤害等级，下载不等于研究准入。PA公共日期限制保留。\n'
readme+='- Denver主政府源为`Denver_official_traffic_accident_offenses`；另存的Colorado Community旧镜像字段有错位，放在`_source`和`_undated`，不得拿它作按年研究数据。\n'
readme+='- FARS为全国死亡事故，早期年份不保证有可用经纬度；辅助CSV不是额外事故。\n'
readme+='- 人员/车辆行不是独立事故；归档中多种表/源可能描述同一事故。文件数和行数不代表唯一事故数。\n\n'
readme+='## 下载与完整性清单\n\n'
readme+='`manifests/acquisition/download_inventory.csv`列文件、年份、记录数、字节数、来源和SHA256；`all_job_status.json`列完成/空/失败；`all_sources.json`列源覆盖和条件。\n\n'
readme+=f"最终SHA256及快照行数审计：{sum(x['status']=='passed' for x in checks)}项通过，{sum(x['status']=='issues' for x in checks)}项有问题。原始ZIP/XLSX的CRC以及CSV行/列验证在下载时已执行。\n\n"
readme+='已定位的源文件异常：CA/2025/Parties_2025.csv.gz 第151090条CSV记录（含表头），表头48列、该行50列。已用官方HTTP字节范围查询确认源文件与归档异常行完全一致，原始字节保持不变；详见 `docs/source_metadata/CA/Parties_2025_source_row_anomaly.json`。SHA256/大小核对均通过，此问题是源CSV行宽异常。\n\n'
readme+='本轮扩展见 `manifests/acquisition/expansion_review.md`。Florida后续下载依用户指示停止；未完成计划项单列 `expansion_deferred.json`，临时片段在 `_partial/FL`，不算成功数据。Washington CSV有两行官方说明，读取时使用skiprows=2；ReportNumber不保证全局唯一，保留官方所有行。CO新增仅Jefferson County县级数据，不代表全州。NC的空间点层仅K/A伤亡事故，主表无坐标；TN新增仅伤亡事故。NY州公开表缺坐标，MN公开CSV缺标准碰撞类型。MN有若干源CSV行宽异常，原始ZIP保留，逐文件metadata已标记；大小/哈希错误与原始格式异常分开解释。\n\n'
readme+='未取得的来源：\n\n'
for item in blocked:readme+='- '+item['region']+'：'+item['reason']+'\n'
unresolved=[j for j in job_status if j['status'] not in ['complete','empty']]
if unresolved:
    readme+='\n尚未完成的计划项：\n\n'
    for job in unresolved:readme+='- '+job['id']+'：'+job['status']+'\n'
(d.ROOT/'README.md').write_text(readme,encoding='utf-8')
result={'files':len(complete),'regions':len(summary),'stored_bytes':sum(g['bytes'] for g in summary.values()),
        'integrity_issues':sum(x['status']=='issues' for x in checks),'unresolved_jobs':len(unresolved),'empty_year_directories_removed':len(removed)}
d.atomic_json(d.MANIFEST/'final_result.json',result)
print('FINAL ARCHIVE AUDIT',json.dumps(result),flush=True)
