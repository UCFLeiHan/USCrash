import os, time, zipfile
from pathlib import Path
import requests

ROOT = Path(r'F:\LH_Research\USCrash\Crash\States\NJ')
BASE = 'https://www.nj.gov/transportation/refdata/accident'
TABLES = ['Accidents', 'Drivers', 'Vehicles', 'Occupants', 'Pedestrians']
session = requests.Session()

def download(url, destination):
    partial = destination.with_suffix(destination.suffix + '.partial')
    for attempt in range(6):
        try:
            with session.get(url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with partial.open('wb') as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            os.replace(partial, destination)
            return
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)

ROOT.mkdir(parents=True, exist_ok=True)
(ROOT/'README.txt').write_text(
    'Official NJDOT statewide crash tables, 2001-2018.\n'
    'https://dot.nj.gov/transportation/refdata/accident/rawdata01-current.shtm\n'
    'The five tables join on year, county code, municipality code, and department case number.\n',
    encoding='utf-8')
for year in range(2018, 2000, -1):
    directory = ROOT / str(year); raw = directory / 'Raw'; raw.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        name = f'NewJersey{year}{table}.zip'
        archive = raw / name
        if not archive.exists():
            download(f'{BASE}/{year}/{name}', archive)
        with zipfile.ZipFile(archive) as bundle:
            members = [m for m in bundle.namelist() if not m.endswith('/')]
            if not members:
                raise RuntimeError(f'Empty archive: {archive}')
            for member in members:
                target = directory / f'NJ_{table.lower()}_{year}.csv'
                if not target.exists():
                    with bundle.open(member) as source, target.open('wb') as output:
                        output.write(source.read())
        print(year, table, archive.stat().st_size, flush=True)
