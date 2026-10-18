import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\MS")
BASE = "https://publicdata.dps.ms.gov/Public-CrashData"
LOG = ROOT / "download.log"
MANIFEST = ROOT / "docs/source_metadata" / "download_manifest.json"


def log(message):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", "replace")


def page_links(url):
    text = fetch_text(url)
    links = re.findall(r'href=["\']([^"\']+)', text, flags=re.I)
    resolved = []
    for link in links:
        absolute = urllib.parse.urljoin(url, html.unescape(link))
        parts = urllib.parse.urlsplit(absolute)
        resolved.append(urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%"), parts.query, parts.fragment)))
    return resolved


def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.exists() and destination.stat().st_size > 1000:
        log(f"SKIP {destination} ({destination.stat().st_size:,} bytes)")
        return destination.stat().st_size
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=300) as response, partial.open("wb") as out:
                expected = int(response.headers.get("Content-Length", "0") or 0)
                copied = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    copied += len(chunk)
                if expected and copied != expected:
                    raise IOError(f"short download: expected {expected}, got {copied}")
            partial.replace(destination)
            log(f"DONE {destination} ({copied:,} bytes)")
            return copied
        except Exception as exc:
            log(f"RETRY {attempt}/4 {url}: {exc}")
            time.sleep(attempt * 5)
    raise RuntimeError(f"failed after retries: {url}")


def main():
    (ROOT / "docs/source_metadata").mkdir(parents=True, exist_ok=True)
    entries = []

    ecrash_url = f"{BASE}/eCrash/"
    ecrash_links = page_links(ecrash_url)
    annual = []
    for url in ecrash_links:
        decoded = urllib.parse.unquote(url)
        match = re.search(r"\((\d{2})-01-01 to \1-12-31\)", decoded)
        if match and decoded.lower().endswith(".xlsx"):
            year = 2000 + int(match.group(1))
            annual.append((year, url))
    for year, url in sorted(annual, reverse=True):
        name = f"mississippi_ecrash_{year}.xlsx"
        size = download(url, ROOT / str(year) / name)
        entries.append({"year": year, "system": "eCrash", "url": url, "file": str(ROOT / str(year) / name), "bytes": size})

    mapping = next((u for u in ecrash_links if "Column%20Mapping" in u or "Column Mapping" in urllib.parse.unquote(u)), None)
    if mapping:
        download(mapping, ROOT / "docs/source_metadata" / "eCrash_ReportBeam_column_mapping.xlsx")

    reportbeam_url = f"{BASE}/ReportBeam/"
    reportbeam_links = page_links(reportbeam_url)
    rb = []
    for url in reportbeam_links:
        match = re.search(r"ReportBeam-(20\d{2})-CrashData\.zip$", urllib.parse.unquote(url), re.I)
        if match:
            rb.append((int(match.group(1)), url))
    for year, url in sorted(rb, reverse=True):
        name = f"mississippi_reportbeam_{year}.zip"
        size = download(url, ROOT / str(year) / name)
        entries.append({"year": year, "system": "ReportBeam", "url": url, "file": str(ROOT / str(year) / name), "bytes": size})

    codes = next((u for u in reportbeam_links if u.lower().endswith("reportbeamcodevaluetable.txt")), None)
    if codes:
        download(codes, ROOT / "docs/source_metadata" / "ReportBeamCodeValueTable.txt")

    MANIFEST.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    log(f"COMPLETE {len(entries)} annual source files")


if __name__ == "__main__":
    main()
