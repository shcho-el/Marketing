# 바탕화면(및 선택 시 시작 프로그램)에 바로가기를 만든다.
#
# 주의: 이 파일은 반드시 'UTF-8 BOM 있음'으로 저장해야 한다.
# Windows PowerShell 5.1은 BOM이 없으면 .ps1을 시스템 기본 인코딩(한국어 윈도우=cp949)
# 으로 읽어 한글이 깨지고, 깨진 이름에 '?'가 섞여 파일 저장까지 실패한다.
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$target = Join-Path $root "launch.bat"
$icon   = Join-Path $root "assets\obliv.ico"

if (-not (Test-Path $target)) { throw "launch.bat 을 찾지 못했습니다: $target" }

# ── 바탕화면 경로 찾기 ────────────────────────────────────────────
# OneDrive로 바탕화면이 옮겨진 PC가 많아 후보를 차례로 확인한다.
function Get-DesktopPath {
  $candidates = @(
    [Environment]::GetFolderPath("DesktopDirectory"),
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:USERPROFILE "Desktop")
  )
  foreach ($v in @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer)) {
    if ($v) { $candidates += (Join-Path $v "Desktop") }
  }
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c -PathType Container)) { return $c }
  }
  return $null
}

$desktop = Get-DesktopPath
if (-not $desktop) { throw "바탕화면 폴더를 찾지 못했습니다." }

# 파일명에 쓸 수 없는 문자가 섞이면 저장이 실패한다. 미리 걸러 낸다.
function Clean-Name([string]$name) {
  $bad = [IO.Path]::GetInvalidFileNameChars()
  $sb = New-Object System.Text.StringBuilder
  foreach ($ch in $name.ToCharArray()) {
    if ($bad -notcontains $ch) { [void]$sb.Append($ch) }
  }
  return $sb.ToString()
}

# 한글이 깨진 채로 실행되면(=BOM 없이 읽힘) 이름이 망가진다. 그때는 영문 이름을 쓴다.
$consoleName = "오블리브 콘텐츠 콘솔"
$webName     = "오블리브 콘텐츠 생성기 (웹)"
if ($consoleName -match '[\?�]' -or $consoleName.Length -ne 11) {
  Write-Host "  (한글 인코딩이 깨져 영문 이름으로 만듭니다)" -ForegroundColor Yellow
  $consoleName = "Obliv Content Console"
  $webName     = "Obliv Content Studio (Web)"
}

function New-Link($path) {
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut($path)
  $lnk.TargetPath       = $target
  $lnk.WorkingDirectory = $root
  $lnk.Description      = "Obliv content console"
  $lnk.WindowStyle      = 7          # 최소화로 시작
  if (Test-Path $icon) { $lnk.IconLocation = "$icon,0" }
  $lnk.Hotkey           = "CTRL+ALT+O"
  $lnk.Save()
  if (-not (Test-Path -LiteralPath $path)) { throw "바로가기를 저장하지 못했습니다: $path" }
}

$lnkPath = Join-Path $desktop ((Clean-Name $consoleName) + ".lnk")
New-Link $lnkPath

Write-Host ""
Write-Host "  바탕화면에 바로가기를 만들었습니다." -ForegroundColor Green
Write-Host "    $lnkPath"
Write-Host "    단축키   Ctrl + Alt + O"

# ── 클라우드 웹앱(브라우저 전용) 바로가기 ─────────────────────────
$webUrl = "https://claude.ai/code/artifact/0a65c72b-d85f-41bf-8c00-ea62ba8c0ec2"
$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
  foreach ($line in (Get-Content -LiteralPath $envPath)) {
    if ($line -match '^\s*WEBAPP_URL\s*=\s*(\S+)\s*$') { $webUrl = $Matches[1] }
  }
}

if ($webUrl -and $webUrl -match '^https?://') {
  $urlPath = Join-Path $desktop ((Clean-Name $webName) + ".url")
  $lines = @("[InternetShortcut]", "URL=$webUrl")
  if (Test-Path $icon) {
    $lines += "IconFile=$icon"
    $lines += "IconIndex=0"
  }
  Set-Content -LiteralPath $urlPath -Value $lines -Encoding ASCII
  Write-Host ""
  Write-Host "    $urlPath" -ForegroundColor Green
  Write-Host "    주소     $webUrl"
}

Write-Host ""
$ans = Read-Host "  PC를 켤 때 자동으로 실행할까요? (y/N)"
if ($ans -match '^[yY]') {
  $startup = [Environment]::GetFolderPath("Startup")
  if ($startup -and (Test-Path -LiteralPath $startup)) {
    New-Link (Join-Path $startup ((Clean-Name $consoleName) + ".lnk"))
    Write-Host "  시작 프로그램에도 등록했습니다." -ForegroundColor Green
  } else {
    Write-Host "  시작 프로그램 폴더를 찾지 못해 건너뜁니다." -ForegroundColor Yellow
  }
} else {
  Write-Host "  시작 프로그램 등록은 건너뜁니다."
}
Write-Host ""
