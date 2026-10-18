"""One command for the representative-year replay, including documented repairs and overlays.
Set USCRASH_REPLAY_ROOT to a fresh isolated directory for an independent rerun.
Existing per-state reports are checkpoints, not evidence of a fresh execution.
"""
import json,subprocess,sys
from replay_representative_years import W,L
def run(name,*args):subprocess.run([sys.executable,str(L/'reproducibility'/name),*args],check=True)
run('replay_representative_years.py')
for p in sorted(W.glob('*/report.json')):
 r=json.loads(p.read_text(encoding='utf-8-sig'));st=r['state']
 if r['status']=='ERROR':
  logs='\n'.join(q.read_text(encoding='utf-8-sig',errors='replace') for q in p.parent.glob('*harmonize*.log'))
  if 'UnboundLocalError' in logs and 'manner_prov' in logs:run('recheck_base_and_fix.py',st)
 if st in {'CT','ID','MS'} and not r.get('byte_identical'):run('recheck_base_and_fix.py',st)
for st in ['CA','MA','NC','NJ','TX']:
 r=json.loads((W/st/'report.json').read_text(encoding='utf-8-sig'))
 if not r.get('byte_identical'):run('replay_coordinate_stages.py',st)
r=json.loads((W/'WA/report.json').read_text(encoding='utf-8-sig'))
if not r.get('dependency_years'):run('replay_wa_union.py')
run('summarize_representative_replay.py')
