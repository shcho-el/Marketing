# Creates desktop shortcuts for the Obliv content console.
#
# This file is intentionally PURE ASCII.  Windows PowerShell 5.1 reads a .ps1
# without a BOM using the system codepage (cp949 on Korean Windows), which
# mangles any non-ASCII text in the source.  A mangled name can contain '?',
# which is illegal in a Windows filename, and the save then fails.
# So the Korean names are built from code points instead of literals.
$ErrorActionPreference = "Stop"
$VERSION = "v2"

function U([int[]]$codes) { -join ($codes | ForEach-Object { [char]$_ }) }

# "Obliv Content Console" in Korean
$CONSOLE_NAME = U @(0xC624,0xBE14,0xB9AC,0xBE0C,0x0020,0xCF58,0xD150,0xCE20,0x0020,0xCF58,0xC194)
# "Obliv Content Studio (Web)" in Korean
$WEB_NAME = U @(0xC624,0xBE14,0xB9AC,0xBE0C,0x0020,0xCF58,0xD150,0xCE20,0x0020,
                0xC0DD,0xC131,0xAE30,0x0020,0x0028,0xC6F9,0x0029)

Write-Host ""
Write-Host "  make_shortcut $VERSION"

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$target = Join-Path $root "launch.bat"
$icon   = Join-Path $root "assets\obliv.ico"

if (-not (Test-Path -LiteralPath $target)) {
  throw "launch.bat not found: $target"
}

# --- Desktop folder (OneDrive redirection is common) ----------------
function Get-DesktopPath {
  $c = @(
    [Environment]::GetFolderPath("DesktopDirectory"),
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:USERPROFILE "Desktop")
  )
  foreach ($v in @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer)) {
    if ($v) { $c += (Join-Path $v "Desktop") }
  }
  foreach ($p in $c) {
    if ($p -and (Test-Path -LiteralPath $p -PathType Container)) { return $p }
  }
  return $null
}

$desktop = Get-DesktopPath
if (-not $desktop) { throw "Desktop folder not found." }

function Clean-Name([string]$name) {
  $bad = [IO.Path]::GetInvalidFileNameChars()
  $sb = New-Object System.Text.StringBuilder
  foreach ($ch in $name.ToCharArray()) {
    if ($bad -notcontains $ch) { [void]$sb.Append($ch) }
  }
  $sb.ToString()
}

function New-Link([string]$path) {
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut($path)
  $lnk.TargetPath       = $target
  $lnk.WorkingDirectory = $root
  $lnk.Description      = "Obliv content console"
  $lnk.WindowStyle      = 7
  if (Test-Path -LiteralPath $icon) { $lnk.IconLocation = "$icon,0" }
  $lnk.Hotkey = "CTRL+ALT+O"
  $lnk.Save()
  if (-not (Test-Path -LiteralPath $path)) { throw "Could not save shortcut: $path" }
}

$lnkPath = Join-Path $desktop ((Clean-Name $CONSOLE_NAME) + ".lnk")
New-Link $lnkPath
Write-Host ""
Write-Host "  Created:" -ForegroundColor Green
Write-Host "    $lnkPath"
Write-Host "    Hotkey: Ctrl + Alt + O"

# --- Browser shortcut to the cloud web app --------------------------
$webUrl = "https://claude.ai/code/artifact/0a65c72b-d85f-41bf-8c00-ea62ba8c0ec2"
$envPath = Join-Path $root ".env"
if (Test-Path -LiteralPath $envPath) {
  foreach ($line in (Get-Content -LiteralPath $envPath)) {
    if ($line -match '^\s*WEBAPP_URL\s*=\s*(\S+)\s*$') { $webUrl = $Matches[1] }
  }
}
if ($webUrl -and $webUrl -match '^https?://') {
  $urlPath = Join-Path $desktop ((Clean-Name $WEB_NAME) + ".url")
  $lines = @("[InternetShortcut]", "URL=$webUrl")
  if (Test-Path -LiteralPath $icon) { $lines += "IconFile=$icon"; $lines += "IconIndex=0" }
  Set-Content -LiteralPath $urlPath -Value $lines -Encoding ASCII
  Write-Host "    $urlPath" -ForegroundColor Green
}

Write-Host ""
$ans = Read-Host "  Run automatically at startup? (y/N)"
if ($ans -match '^[yY]') {
  $startup = [Environment]::GetFolderPath("Startup")
  if ($startup -and (Test-Path -LiteralPath $startup)) {
    New-Link (Join-Path $startup ((Clean-Name $CONSOLE_NAME) + ".lnk"))
    Write-Host "  Registered at startup." -ForegroundColor Green
  }
}
Write-Host ""
