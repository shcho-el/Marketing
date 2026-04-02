# 오블리브 키워드 순위 수집 - Windows 작업 스케줄러 자동 등록
# PowerShell을 관리자 권한으로 실행 후 이 스크립트를 실행하세요

$TaskName = "ObliveKeywordRanking"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatFile = Join-Path $ProjectDir "run_collect.bat"

# logs 폴더 생성
$LogDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "logs 폴더 생성 완료" -ForegroundColor Green
}

# 기존 작업 제거 (있으면)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "기존 작업 제거됨" -ForegroundColor Yellow
}

# 트리거: 매일 오전 8시
$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

# 실행 액션: run_collect.bat
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatFile`""

# 설정: 배터리 상태에서도 실행, 놓친 작업 즉시 실행
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable

# 현재 사용자로 등록
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Principal $Principal `
    -Description "오블리브 네이버 키워드 순위 매일 오전 8시 자동 수집 + 슬랙 알림" | Out-Null

Write-Host ""
Write-Host "✅ 작업 스케줄러 등록 완료!" -ForegroundColor Green
Write-Host "   작업 이름 : $TaskName" -ForegroundColor Cyan
Write-Host "   실행 시각 : 매일 오전 08:00" -ForegroundColor Cyan
Write-Host "   로그 위치 : $LogDir\collect.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "지금 바로 테스트 실행하려면:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
