"""Sequential coordinate overlay runner. Default: audit only; --apply applies reviewed overlays."""
import argparse,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();root=Path(__file__).parent
steps=[('supplement_al_care_coordinates.py',None),('supplement_nc_ka_coordinates.py',None),('supplement_nc_public_mapped_layers.py',None),('supplement_nj_dvrpc_coordinates.py',None),('supplement_oh_cleveland_coordinates.py','Cleveland'),('supplement_oh_cleveland_coordinates.py','Columbus'),('supplement_tx_austin_coordinates.py',None),('supplement_ma_archived_geometry.py',None),('supplement_id_published_geometry.py',None)]
if a.apply:
 for script,city in steps:
  env=os.environ.copy()
  if city:env['USCRASH_OH_CITY']=city
  subprocess.run([sys.executable,str(root/script)],env=env,check=True)
subprocess.run([sys.executable,str(root/'audit_coordinate_recovery.py')],check=True)
