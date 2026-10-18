"""Refresh current release summaries after an audited FL promotion; no raw writes."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

U=Path(__file__).resolve().parents[1]
R=U/'qa/revisions/2026-10-14_FL_codeable_fhe'

def run(name,*args):
    subprocess.run([sys.executable,str(U/'scripts'/name),*args],check=True)

def main():
    revision=json.loads((R/'promotion_manifest.json').read_text())
    assert revision['result']=='PASS'
    for script in ['audit_all_state_annual_integrity.py','build_final_42_state_integrity_audit.py',
                   'audit_unified_storage.py','summarize_harmonization.py']:run(script)
    audit=json.loads((U/'qa/cross_state/final_42_state_integrity_audit.json').read_text())
    old=json.loads((R/'before/cross_state/final_42_state_integrity_audit.json').read_text())
    assert audit['result']=='PASS' and audit['data_state_count']==42
    total=audit['total_harmonized_records']
    assert total==old['total_harmonized_records']-revision['excluded_codeable_n']
    assert audit['data_states']['FL']['rows']==revision['canonical_fl_rows_after']
    for state in old['data_states']:
        if state!='FL':assert audit['data_states'][state]==old['data_states'][state],state
    run('plot_spatiotemporal_quality.py','--workers','2')
    run('build_external_validation_and_eligibility.py')
    card=U/'DATASET_CARD.md';text=card.read_text(encoding='utf-8')
    text=re.sub(r'- Unique crash records: [\d,]+',f'- Unique crash records: {total:,}',text)
    start=text.index('The 2026-10-14 external review is separate')
    stop=text.index('The final audit confirms',start)
    corrected=(
        'The 2026-10-14 external review is separate from internal integrity validation. '
        'Florida 2020–2025 canonical outputs now select raw `CODEABLE=Y`; '
        f'{revision["excluded_codeable_n"]:,} CODEABLE=N reports were excluded from this research population, '
        'with original sources, excluded-ID ledgers and preceding outputs retained. N does not itself mean invalid or duplicate. '
        'Legacy FDOT years have no equivalent verified filter and retain their original source populations. '
        'FL 2023 retains 393,241 codeable reports against 395,175 in the official annual snapshot; '
        'the remaining 1,934-report difference is unresolved and was not force-adjusted.\n\n'
        'Florida 2011–2019 no longer maps `MOST_HARM_EVNT_CD` into first harmful event. '
        'First-event values and dependent groups are blank with UNAVAILABLE provenance; '
        'most-event observations remain available in the versioned correction sidecar and raw inputs. '
        'All other retained canonical cells were checked for exact equality against the preceding output.\n\n'
        'Missouri public-layer/local counts for 2024 and 2025 are substantially below the preserved preliminary annual-report snapshots '
        '(−42.51% and −67.36% respectively). Those files remain available as source extracts, but are excluded '
        'from complete-state annual totals. MO 2026 is YTD with unverified source completeness, '
        'not a verified full-state sample. North Carolina remains unchanged under its accepted public-table population; '
        'its counts must not be described as the distinct published reportable-crash totals. '
        'See `qa/external_validation_2026-10-14/` and `qa/revisions/2026-10-14_FL_codeable_fhe/` '
        'for definitions, reference versions, row-level evidence and executable rules.\n\n')
    text=text[:start]+corrected+text[stop:];card.write_text(text,encoding='utf-8')
    readme=U/'README.md';text=readme.read_text(encoding='utf-8')
    old_line='- `analysis_views/FL_CODEABLE_Y/`: separately filtered Florida comparison tables; never append these views to the canonical crash data.'
    new_line='- `analysis_views/FL_CODEABLE_Y/`: earlier Florida comparison copies. Current formal 2020–2025 outputs already select CODEABLE=Y; these copies must never be appended to canonical data.\n- `qa/revisions/2026-10-14_FL_codeable_fhe/`: population-selection and first-event correction audit, excluded IDs, most-event sidecar and preceding outputs.'
    if old_line in text:text=text.replace(old_line,new_line)
    readme.write_text(text,encoding='utf-8')
    result=dict(revision_id=R.name,completed_utc=datetime.now(timezone.utc).isoformat(),
                formal_jurisdictions=42,annual_csv_files=511,total_current_records=total,
                other_jurisdictions_unchanged=True,internal_integrity='PASS',
                raw_data_not_modified=True,external_completeness_not_certified=True,
                refreshed=['national_integrity','harmonization_progress','spatiotemporal_plots',
                           'external_validation','eligibility','DATASET_CARD.md','README.md'])
    result['script_sha256']={name:hashlib.sha256((U/'scripts'/name).read_bytes()).hexdigest()
         for name in ['harmonize_crash.py','verify_promote_fl_revision.py',
                      'audit_mo_recent_coverage.py','build_external_validation_and_eligibility.py',
                      'plot_spatiotemporal_quality.py',Path(__file__).name]}
    (R/'finalization_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
