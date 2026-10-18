param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Z]{2}$')][string]$State,
    [string]$DataRoot = 'F:\LH_Research\USCrash\Crash',
    [string]$Python = 'D:\Anaconda\python.exe'
)

$ErrorActionPreference = 'Stop'
$env:USCRASH_ROOT = (Resolve-Path -LiteralPath $DataRoot).Path
$pipelineRoot = Join-Path $env:USCRASH_ROOT 'Unified_MMUCC6'
$scripts = Join-Path $env:USCRASH_ROOT 'code\processing'

if ($State -eq 'WA') {
    & $Python (Join-Path $scripts 'build_wa_crash_level.py')
    if ($LASTEXITCODE -ne 0) { throw 'WA CAT preparation failed' }
}

& $Python (Join-Path $scripts 'profile_state_codes.py') --state $State
if ($LASTEXITCODE -ne 0) { throw "Source profiling failed for $State" }

& $Python (Join-Path $scripts 'harmonize_crash.py') --state $State
if ($LASTEXITCODE -ne 0) { throw "Harmonization failed for $State" }

if ($State -eq 'WA') {
    & $Python (Join-Path $scripts 'enrich_wa_from_srff.py') --promote
    if ($LASTEXITCODE -ne 0) { throw 'WA SRFF enrichment failed' }
}

& $Python (Join-Path $scripts 'validate_harmonized_crash.py') --state $State
if ($LASTEXITCODE -ne 0) { throw "Post-harmonization validation failed for $State" }

Write-Host "Pipeline completed successfully for $State"
