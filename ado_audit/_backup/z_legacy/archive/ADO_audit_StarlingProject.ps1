# Get the path to the PAT file in the same directory as the script
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path $scriptPath
$patFilePath = Join-Path $scriptDir "ado_pat.txt"

# Read the PAT from the file
if (Test-Path $patFilePath) {
    $pat = Get-Content $patFilePath -Raw
    $base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$pat"))
    $headers = @{ Authorization = "Basic $base64AuthInfo" }
} else {
    Write-Host "❌ PAT file not found at: $patFilePath"
    return
}
