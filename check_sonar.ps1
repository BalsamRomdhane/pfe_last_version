$base = "http://localhost:9000"
$user = "admin"
$pass = "admin"
$bytes = [Text.Encoding]::ASCII.GetBytes("${user}:${pass}")
$b64 = [Convert]::ToBase64String($bytes)
$headers = @{ Authorization = "Basic $b64" }

Write-Host "`n=== SonarQube Server ===" -ForegroundColor Cyan
$status = Invoke-RestMethod -Uri "$base/api/system/status" -UseBasicParsing
Write-Host "Version : $($status.version)"
Write-Host "Status  : $($status.status)"

Write-Host "`n=== Project Search: enterprise-iso-compliance ===" -ForegroundColor Cyan
try {
    $proj = Invoke-RestMethod -Uri "$base/api/projects/search?projects=enterprise-iso-compliance" -Headers $headers -UseBasicParsing
    if ($proj.components.Count -gt 0) {
        $p = $proj.components[0]
        Write-Host "EXISTS  : YES"
        Write-Host "Key     : $($p.key)"
        Write-Host "Name    : $($p.name)"
        Write-Host "Visibility: $($p.visibility)"
    } else {
        Write-Host "EXISTS  : NO - project not found" -ForegroundColor Red
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Tokens for project ===" -ForegroundColor Cyan
try {
    $tokens = Invoke-RestMethod -Uri "$base/api/user_tokens/search" -Headers $headers -UseBasicParsing
    $tokens.userTokens | ForEach-Object {
        Write-Host "Token: $($_.name) | Type: $($_.type) | Created: $($_.createdAt) | LastUsed: $($_.lastConnectionDate)"
    }
} catch {
    Write-Host "ERROR listing tokens: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Default permissions template ===" -ForegroundColor Cyan
try {
    $perms = Invoke-RestMethod -Uri "$base/api/permissions/search_templates" -Headers $headers -UseBasicParsing
    $perms.permissionTemplates | ForEach-Object {
        Write-Host "Template: $($_.name) | Default: $($_.defaultFor)"
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Jenkins port check ===" -ForegroundColor Cyan
try {
    $jenkins = Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 5
    Write-Host "Jenkins at :8080 - Status: $($jenkins.StatusCode)"
} catch {
    try {
        $jenkins = Invoke-WebRequest -Uri "http://localhost:8089" -UseBasicParsing -TimeoutSec 5
        Write-Host "Jenkins at :8089 - Status: $($jenkins.StatusCode)"
    } catch {
        Write-Host "Jenkins not reachable on :8080 or :8089" -ForegroundColor Yellow
    }
}

Write-Host "`n=== sonar-project.properties ===" -ForegroundColor Cyan
Get-Content "c:\Users\balsa\lastversion\sonar-project.properties" | ForEach-Object {
    if ($_ -notmatch "^#" -and $_.Trim() -ne "") {
        Write-Host $_
    }
}
