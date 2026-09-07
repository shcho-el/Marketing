# 바탕화면(및 선택 시 시작 프로그램)에 바로가기를 만든다.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root    = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$target  = Join-Path $root "launch.bat"
$icon    = Join-Path $root "assets\obliv.ico"
$name    = "오블리브 콘텐츠 콘솔.lnk"
$desktop = [Environment]::GetFolderPath("Desktop")

if (-not (Test-Path $target)) { throw "launch.bat 을 찾지 못했습니다: $target" }

function New-Link($path) {
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut($path)
  $lnk.TargetPath       = $target
  $lnk.WorkingDirectory = $root
  $lnk.Description      = "오블리브 콘텐츠 콘솔 열기"
  $lnk.WindowStyle      = 7          # 최소화로 시작
  if (Test-Path $icon) { $lnk.IconLocation = "$icon,0" }
  $lnk.Hotkey           = "CTRL+ALT+O"
  $lnk.Save()
}

New-Link (Join-Path $desktop $name)
Write-Host ""
Write-Host "  바탕화면에 바로가기를 만들었습니다." -ForegroundColor Green
Write-Host "    이름     오블리브 콘텐츠 콘솔  (이 PC에서 서버 실행)"
Write-Host "    단축키   Ctrl + Alt + O"

# ── 클라우드 웹앱(브라우저 전용) 바로가기 ─────────────────────────
# .env 의 WEBAPP_URL 을 쓰고, 없으면 아래 기본값을 쓴다.
$webUrl = "https://claude.ai/code/artifact/0a65c72b-d85f-41bf-8c00-ea62ba8c0ec2"
$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
  foreach ($line in Get-Content $envPath -Encoding UTF8) {
    if ($line -match '^\s*WEBAPP_URL\s*=\s*(\S+)') { $webUrl = $Matches[1] }
  }
}

if ($webUrl -and $webUrl -match '^https?://') {
  $webName = "오블리브 콘텐츠 생성기 (웹).url"
  $webPath = Join-Path $desktop $webName
  $lines = @("[InternetShortcut]", "URL=$webUrl")
  if (Test-Path $icon) {
    $lines += "IconFile=$icon"
    $lines += "IconIndex=0"
  }
  Set-Content -Path $webPath -Value $lines -Encoding ASCII
  Write-Host ""
  Write-Host "    이름     오블리브 콘텐츠 생성기 (웹)  (브라우저에서 바로)" -ForegroundColor Green
  Write-Host "    주소     $webUrl"
}
Write-Host ""

$ans = Read-Host "  PC를 켤 때 자동으로 실행할까요? (y/N)"
if ($ans -match '^[yY]') {
  $startup = [Environment]::GetFolderPath("Startup")
  New-Link (Join-Path $startup $name)
  Write-Host "  시작 프로그램에도 등록했습니다." -ForegroundColor Green
} else {
  Write-Host "  시작 프로그램 등록은 건너뜁니다."
}
Write-Host ""
