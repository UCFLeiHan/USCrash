$ErrorActionPreference='Stop'
$mnUrl='https://mncrash.state.mn.us/Pages/AdHocSearch.aspx'
$metaRoot='US/docs/source_metadata/expansion'
function Prepare-MnBody([string]$page,[string]$target='',[string]$argument='') {
    & D:\Anaconda\python.exe -X utf8 US/acquisition/prepare_web_form.py $page "$metaRoot/MN_form.json" $target $argument
    if ($LASTEXITCODE -ne 0) { throw 'Form preparation failed' }
    $form=Get-Content "$metaRoot/MN_form.json" -Raw | ConvertFrom-Json
    $body=@{}; $form.PSObject.Properties | ForEach-Object { $body[$_.Name]=[string]$_.Value }
    return $body
}
foreach ($crashYear in 2016..2026) {
    $receipt="US/MN/$crashYear/MnCrash_public_collisions_$crashYear.zip.metadata.json"
    if (Test-Path -LiteralPath $receipt) { continue }
    $initial=Invoke-WebRequest -Uri $mnUrl -UseBasicParsing -SessionVariable mnExportSession -TimeoutSec 60
    $initial.Content | Set-Content -Encoding UTF8 "$metaRoot/MN_current.txt"
    $body=Prepare-MnBody "$metaRoot/MN_current.txt" 'ctl00$ContentPlaceHolder$QueryPanel1$r1$e2' '7'
    $custom=Invoke-WebRequest -Uri $mnUrl -Method Post -Body $body -WebSession $mnExportSession -UseBasicParsing -TimeoutSec 60
    $custom.Content | Set-Content -Encoding UTF8 "$metaRoot/MN_current.txt"
    $body=Prepare-MnBody "$metaRoot/MN_current.txt"
    $body['ContentPlaceHolder_QueryPanel1_r1_e3_DatePanel_textbox']="01/01/$crashYear"
    $body['ContentPlaceHolder_QueryPanel1_r1_e5_DatePanel_textbox']="12/31/$crashYear"
    $body['ctl00$ContentPlaceHolder$btnSearch']='Search'
    $search=Invoke-WebRequest -Uri $mnUrl -Method Post -Body $body -WebSession $mnExportSession -UseBasicParsing -TimeoutSec 120
    $search.Content | Set-Content -Encoding UTF8 "$metaRoot/MN_search$crashYear.txt"
    $countMatch=[regex]::Match($search.Content,'id="ContentPlaceHolder_lblTotalCollisions"[^>]*>([\d,]+)<')
    if (-not $countMatch.Success) { throw "No official row count for $crashYear" }
    $expected=[int]($countMatch.Groups[1].Value.Replace(',',''))
    $body=Prepare-MnBody "$metaRoot/MN_search$crashYear.txt"
    $body['ctl00$ContentPlaceHolder$rdoListExportOptions']='CSV'; $body['ctl00$ContentPlaceHolder$btnExport']='Export'
    $export=Invoke-WebRequest -Uri $mnUrl -Method Post -Body $body -WebSession $mnExportSession -UseBasicParsing -TimeoutSec 120 -OutFile "$metaRoot/MN_export$crashYear.probe" -PassThru
    if ($export.Headers['Content-Type'] -notmatch 'zip') { throw "Expected ZIP export for $crashYear" }
    & D:\Anaconda\python.exe -X utf8 US/acquisition/receipt_mn.py $crashYear "$metaRoot/MN_export$crashYear.probe" $expected
    if ($LASTEXITCODE -ne 0) { throw "Export validation failed for $crashYear" }
}
Write-Output 'MN ALL YEARS COMPLETE'
