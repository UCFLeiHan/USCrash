"""Index every configured annual input header and its current source bindings.

Read-only with respect to source inputs, configurations and canonical data.
This inventories prepared inputs to harmonization, not every raw entity table.
"""
from pathlib import Path
import csv,json,hashlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'States/field_schemas'

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def save(name,rows):
    with (OUT/name).open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    OUT.mkdir(exist_ok=True)
    links=read(ROOT/'manifests/configured_input_output_links.csv')
    schema=read(ROOT/'code/config/canonical_crash_schema.csv')
    # Schema column naming is taken directly from the configured schema file.
    canonical={x['field_name'] for x in schema}
    assert len(canonical)==77
    assert len(links)==511
    states={};annual=[];bindings=[]
    for link in links:
        st=link['state'];year=int(link['year']);path=ROOT/link['input_path']
        cfg=json.loads((ROOT/f'code/config/states/{st}.json').read_text(encoding='utf-8-sig'))
        versions=[v for v in cfg['versions'] if v['schema_id']==link['schema_id'] and v['year_start']<=year<=v['year_end']]
        assert len(versions)==1,(st,year,link['schema_id'])
        version=versions[0]
        with path.open(encoding='utf-8-sig',newline='') as f:fields=next(csv.reader(f))
        assert fields and len(fields)==len(set(fields)),path
        header_hash=hashlib.sha256(json.dumps(fields,ensure_ascii=False,separators=(',',':')).encode('utf8')).hexdigest()
        profile=dict(year=year,schema_id=link['schema_id'],input_path=link['input_path'],output_path=link['output_path'],field_count=len(fields),header_sha256=header_hash,source_fields=fields)
        state=states.setdefault(st,dict(state=st,state_name=cfg['state_name'],basis='All configured annual inputs to harmonization; executable bindings from current state configurations. Inputs may be prepared tables, rather than untouched raw downloads.',configuration=f'code/config/states/{st}.json',annual_inputs=[],configured_bindings=[]))
        state['annual_inputs'].append(profile)
        annual.append({k:v for k,v in dict(state=st,**profile).items() if k!='source_fields'})
        for target,source in version['fields'].items():
            binding=dict(state=st,year=year,schema_id=link['schema_id'],input_path=link['input_path'],target_binding=target,source_binding=source,binding_kind='canonical_field' if target in canonical else 'helper_binding',exact_source_header_match=source in fields)
            bindings.append(binding);state['configured_bindings'].append(binding)
    for st,state in states.items():
        state['years']=sorted(x['year'] for x in state['annual_inputs'])
        state['input_files']=len(state['annual_inputs'])
        (OUT/f'{st}_fields.json').write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf8')
    save('ALL_states_field_map.csv',bindings)
    save('annual_source_schemas.csv',annual)
    (OUT/'README.md').write_text('''# Current source-field inventory

This index covers all 511 configured annual inputs across 41 states and DC.
It reads each actual input header and the applicable current state configuration.
Prepared harmonization inputs are distinguished from untouched original downloads.

- `ST_fields.json`: every annual input header and configured binding for a state.
- `annual_source_schemas.csv`: all annual input paths, schema versions, field counts and header hashes.
- `ALL_states_field_map.csv`: annual source bindings, including preparation/helper bindings.

`exact_source_header_match=false` is a diagnostic, not necessarily an error: some bindings represent unavailable fields or configured expressions. Bindings are not invented or inferred from column names. Derived attributes and entity aggregation remain defined by processing code. The final 77-column schema is `code/config/canonical_crash_schema.csv`, separate from these heterogeneous source headers.

Regenerate from the Crash root with `python code/processing/build_source_field_inventory.py`.
''',encoding='utf8')
    report=dict(states=len(states),annual_inputs=len(annual),configured_bindings=len(bindings),source_data_changed=False,canonical_data_changed=False)
    assert len(states)==42
    (OUT/'inventory_summary.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
