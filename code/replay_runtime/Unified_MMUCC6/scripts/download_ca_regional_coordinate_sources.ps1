$ErrorActionPreference = 'Stop'
$dest = 'F:\LH_Research\USCrash\Crash\States\CA\Local_coordinate_sources_2026-10-16'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$sources = @(
 @{name='SACOG';url='https://services.sacog.org/hosting/rest/services/Transportation/Collision_SACOG_Region/MapServer/0';fields='CASE_ID,ACCIDENT_YEAR,JURIS,COLLISION_DATE,COLLISION_TIME,PRIMARY_RD,SECONDARY_RD,NUMBER_KILLED,NUMBER_INJURED,POINT_X,POINT_Y'},
 @{name='OrangeCounty_TIMS';url='https://services.arcgis.com/UXmFoWC7yDHcDN5Q/arcgis/rest/services/OCTraffic_Collisions/FeatureServer/1';fields='case_id,date_datetime,date_year,coll_date,coll_time,juris,primary_rd,secondary_rd,latitude,longitude,number_killed'},
 @{name='OrangeCounty_CCRS';url='https://www.ocgis.com/arcpub/rest/services/OC_Infrastructure/Traffic/FeatureServer/0';fields='*'}
)
foreach($source in $sources) {
 try {
  $folder=Join-Path $dest $source.name
  New-Item -ItemType Directory -Force -Path $folder | Out-Null
  $metadata=Invoke-RestMethod -Uri ($source.url+'?f=json') -TimeoutSec 60
  $metadata | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath (Join-Path $folder 'metadata.json') -Encoding utf8
  $ids=Invoke-RestMethod -Uri ($source.url+'/query') -Method Post -Body @{f='json';where='1=1';returnIdsOnly='true'} -TimeoutSec 90
  if($ids.error){throw ($ids.error|ConvertTo-Json -Compress)}
  $objects=@($ids.objectIds | Sort-Object)
  $received=0
  for($offset=0;$offset -lt $objects.Count;$offset+=1000){
   $file=Join-Path $folder ('batch_{0:D7}.json' -f $offset)
   if(Test-Path -LiteralPath $file){$batch=Get-Content -LiteralPath $file -Raw|ConvertFrom-Json}
   else {
    $last=[Math]::Min($offset+999,$objects.Count-1)
    $batch=Invoke-RestMethod -Uri ($source.url+'/query') -Method Post -Body @{f='json';objectIds=($objects[$offset..$last]-join ',');outFields=$source.fields;returnGeometry='true';outSR='4326'} -TimeoutSec 90
    if($batch.error){throw ($batch.error|ConvertTo-Json -Compress)}
    $batch|ConvertTo-Json -Depth 40 -Compress|Set-Content -LiteralPath $file -Encoding utf8
   }
   $received+=@($batch.features).Count
  }
  if($received -ne $objects.Count){throw "Count mismatch $received / $($objects.Count)"}
  @{source=$source.url;expected=$objects.Count;downloaded=$received;fields=$source.fields;retrieved=(Get-Date -Format o);coordinate_system='EPSG:4326';status='COMPLETE';canonical_modified=$false}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $folder 'download_manifest.json') -Encoding utf8
  Write-Output "$($source.name) COMPLETE $received"
 } catch {
  Write-Output "$($source.name) FAILED $($_.Exception.Message)"
 }
}
