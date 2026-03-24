# Set variables
$organization = "1id"
$pat = "G2jzdo870EXBrTmVpGTcDjZqD7ROyrdYWJo79GuSD8FArIIXQ2upJQQJ99BFACAAAAAqG6F6AAASAZDO1LW9"
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$pat"))
$headers = @{ Authorization = "Basic $base64AuthInfo" }

# Get all projects
$projectsUrl = "https://dev.azure.com/$organization/_apis/projects?api-version=7.1-preview.4"
$projects = Invoke-RestMethod -Uri $projectsUrl -Headers $headers

foreach ($project in $projects.value) {
    Write-Host "Auditing project: $($project.name)"

    # Get process template
    $processUrl = "https://dev.azure.com/$organization/_apis/projects/$($project.id)/properties?api-version=7.1-preview.1"
    $process = Invoke-RestMethod -Uri $processUrl -Headers $headers
    $processType = ($process.value | Where-Object { $_.name -eq "System.ProcessTemplateType" }).value
    Write-Host "  Process Type: $processType"

    # Get teams
    $teamsUrl = "https://dev.azure.com/$organization/_apis/projects/$($project.id)/teams?api-version=7.1-preview.3"
    $teams = Invoke-RestMethod -Uri $teamsUrl -Headers $headers

    foreach ($team in $teams.value) {
        Write-Host "  Team: $($team.name)"

        # Get area and iteration paths
        $teamSettingsUrl = "https://dev.azure.com/$organization/$($project.name)/_apis/work/teamsettings?team=$($team.name)&api-version=7.1-preview.1"
        $teamSettings = Invoke-RestMethod -Uri $teamSettingsUrl -Headers $headers
        Write-Host "    Backlog Iteration: $($teamSettings.backlogIteration.path)"
        Write-Host "    Working Days: $($teamSettings.workingDays -join ', ')"

        # Get board columns
        $boardUrl = "https://dev.azure.com/$organization/$($project.name)/_apis/work/boards/$($team.name)/columns?api-version=7.1-preview.1"
        try {
            $boardColumns = Invoke-RestMethod -Uri $boardUrl -Headers $headers
            foreach ($column in $boardColumns.value) {
                Write-Host "    Column: $($column.name) (State: $($column.stateMappings.Values -join ', '))"
            }
        } catch {
            Write-Host "    No board configuration found or access issue."
        }
    }
}
