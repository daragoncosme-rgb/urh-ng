# =============================================================================
#  Build URH-NG for Windows 10/11 x64 from this repository
# -----------------------------------------------------------------------------
#  Same steps as the official CI (.github/workflows/ci.yml), for a local PC:
#    1. Install the requirements with winget: Git, Python 3.13, Visual Studio
#       Build Tools (C++ compiler) and Inno Setup.
#    2. Download the prebuilt SDR driver DLLs (HackRF, RTL-SDR, Airspy...).
#    3. Build the Cython/C++ extensions.
#    4. Package with PyInstaller -> portable folder + .zip.
#    5. Build the .exe installer with Inno Setup (data\inno.iss).
#  The decoders in data\decoders are bundled with the portable and installer.
#
#  Usage (normal PowerShell, no administrator rights needed):
#     powershell -ExecutionPolicy Bypass -File data\windows\build_windows.ps1
#  or double-click data\windows\build.bat (also writes a log file).
#
#  Options:
#     -WorkDir D:\path       Folder for the virtualenv, downloads and temp files
#                            (default: <repo>\build-windows)
#     -DepsDir D:\path       Install Python, Git, Build Tools and Inno Setup into
#                            this folder instead of the Windows default (C:)
#     -DecodersDir D:\path   Decoders to bundle (default: <repo>\data\decoders;
#                            "" to bundle none)
#     -NoInstaller           Only build the portable version
#     -NoDependencies        Do not install anything with winget
# =============================================================================
param(
    [string]$WorkDir = "",
    [string]$DepsDir = "",
    [string]$DecodersDir = $null,
    [switch]$NoInstaller,
    [switch]$NoDependencies
)

# "Continue": in Windows PowerShell 5.1, text that external programs write to
# stderr (git, pip, py...) becomes an error record and "Stop" would abort the
# script. Exit codes of external programs are checked by hand instead.
$ErrorActionPreference = "Continue"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"   # cmdlets still stop on errors
$ProgressPreference    = "SilentlyContinue"           # much faster Invoke-WebRequest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Src        = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$SdrDllsUrl = "https://github.com/jopohl/sdrbuild/releases/download/v1.1/win-x64.zip"
$PyVersion  = "3.13"
if (-not $WorkDir) { $WorkDir = Join-Path $Src "build-windows" }
if ($null -eq $DecodersDir) { $DecodersDir = Join-Path $Src "data\decoders" }

function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[x] $m" -ForegroundColor Red; exit 1 }

# Run an external program and abort if it fails
function Run {
    param([string]$Exe, [string[]]$ArgList)
    Write-Host "    > $Exe $($ArgList -join ' ')" -ForegroundColor DarkGray
    $global:LASTEXITCODE = 0
    & $Exe @ArgList 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { Fail "Command failed: $Exe $($ArgList -join ' ') (exit code $LASTEXITCODE)" }
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

# Install locations of the requirements (empty = Windows default)
$PyDir = ""; $GitDir = ""; $VsDir = ""; $InnoDir = ""
function Add-DepsToPath {
    if ($DepsDir) {
        foreach ($d in (Join-Path $PyDir "Scripts"), $PyDir, (Join-Path $GitDir "cmd")) {
            if (Test-Path $d) { $env:Path = "$d;$env:Path" }
        }
    }
}
if ($DepsDir) {
    New-Item -ItemType Directory -Force -Path $DepsDir | Out-Null
    $PyDir   = Join-Path $DepsDir "Python313"
    $GitDir  = Join-Path $DepsDir "Git"
    $VsDir   = Join-Path $DepsDir "BuildTools"
    $InnoDir = Join-Path $DepsDir "InnoSetup6"
    Add-DepsToPath
}

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Find-Python {
    if (Have "py") {
        # No quotes or spaces in the -c argument: PowerShell 5.1 mangles them
        $p = cmd /c "py -$PyVersion -c print(__import__('sys').executable) 2>nul"
        if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() }
    }
    if ($PyDir -and (Test-Path (Join-Path $PyDir "python.exe"))) { return (Join-Path $PyDir "python.exe") }
    $cand = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
    if (Test-Path $cand) { return $cand }
    return $null
}

function Find-Vs {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { return $null }
    $r = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($r) { return $r.Trim() }
    return $null
}

function Find-Iscc {
    if ($InnoDir -and (Test-Path (Join-Path $InnoDir "ISCC.exe"))) { return (Join-Path $InnoDir "ISCC.exe") }
    foreach ($p in @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles      "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA      "Programs\Inno Setup 6\ISCC.exe"))) {
        if (Test-Path $p) { return $p }
    }
    if (Have "iscc") { return (Get-Command iscc).Source }
    return $null
}

function Winget-Install($id, [string[]]$extra = @()) {
    Info "Installing $id with winget..."
    $wgArgs = @("install", "--id", $id, "-e", "--accept-source-agreements", "--accept-package-agreements") + $extra
    & winget @wgArgs
    # winget returns a non-zero code if the package is already installed; checked afterwards
    Refresh-Path
    Add-DepsToPath
}

# --------------------------------------------------------------------------- 0
if (-not [Environment]::Is64BitOperatingSystem) { Fail "A 64-bit Windows is required." }

# --------------------------------------------------------------------------- 1
Info "Checking requirements..."
if (-not $NoDependencies) {
    if (-not (Have "winget")) {
        Fail "winget not found. Install 'App Installer' from the Microsoft Store and run this again."
    }
    if (-not (Have "git")) {
        if ($GitDir) { Winget-Install "Git.Git" @("--override", "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES /DIR=`"$GitDir`"") }
        else         { Winget-Install "Git.Git" }
    }
    if (-not (Find-Python)) {
        if ($PyDir) {
            Winget-Install "Python.Python.$PyVersion" @("--scope", "user", "--override",
                "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 TargetDir=`"$PyDir`"")
        } else {
            Winget-Install "Python.Python.$PyVersion" @("--scope", "user")
        }
    }
    if (-not (Find-Vs)) {
        Warn "Visual Studio Build Tools (C++) will be installed. It is about 3-5 GB and takes a while."
        Warn "Windows will ask for administrator permission: accept it."
        Winget-Install "Microsoft.VisualStudio.2022.BuildTools" @(
            "--override",
            ("--wait --passive --norestart " +
             $(if ($VsDir) { "--installPath `"$VsDir`" " } else { "" }) +
             "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"))
    }
    if (-not $NoInstaller -and -not (Find-Iscc)) {
        if ($InnoDir) { Winget-Install "JRSoftware.InnoSetup" @("--override", "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR=`"$InnoDir`"") }
        else          { Winget-Install "JRSoftware.InnoSetup" }
    }
}

$Python = Find-Python
if (-not $Python)   { Fail "Python $PyVersion is not available. Install it from python.org and restart PowerShell." }
if (-not (Find-Vs)) { Fail "The C++ compiler is missing (Visual Studio Build Tools, 'Desktop development with C++' workload)." }
Info "Python: $Python"

# --------------------------------------------------------------------------- 2
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
Set-Location $Src

$Shared = Join-Path $Src "src\urh\dev\native\lib\shared"
if (-not (Test-Path (Join-Path $Shared "include"))) {
    Info "Downloading the SDR driver DLLs (HackRF, RTL-SDR, Airspy, BladeRF, LimeSDR, PlutoSDR...)..."
    $zip = Join-Path $WorkDir "sdr-win-x64.zip"
    Invoke-WebRequest -Uri $SdrDllsUrl -OutFile $zip -UseBasicParsing
    New-Item -ItemType Directory -Force -Path $Shared | Out-Null
    Expand-Archive -Path $zip -DestinationPath $Shared -Force
}

# --------------------------------------------------------------------------- 3
$Venv = Join-Path $WorkDir "venv"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Info "Creating the Python virtual environment..."
    Run $Python @("-m", "venv", $Venv)
}
$Py = Join-Path $Venv "Scripts\python.exe"

Info "Installing Python dependencies..."
Run $Py @("-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools")
Run $Py @("-m", "pip", "install", "-r", "data\requirements.txt")
Run $Py @("-m", "pip", "install", "pywin32", "pyaudio", "pyinstaller", "packaging", "appdirs")

Info "Building the Cython/C++ extensions..."
# Same as the CI: 'release' marker so the extensions are not rebuilt at start-up
New-Item -ItemType File -Force -Path (Join-Path $env:TEMP "urh_releasing") | Out-Null
Run $Py @("src\urh\cythonext\build.py")

# --------------------------------------------------------------------------- 4
Info "Packaging with PyInstaller (takes a few minutes)..."
foreach ($d in "pyinstaller", "urh_build", "urh_debug_build", "urh_cli_build") {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
}
$env:Path = (Join-Path $Venv "Scripts") + ";" + $env:Path   # so 'pyinstaller' is found
Run $Py @("data\pyinstaller_helper.py")

$AppDir = Join-Path $Src "pyinstaller\urh"
if (-not (Test-Path (Join-Path $AppDir "urh.exe"))) { Fail "PyInstaller did not create urh.exe." }

Info "Testing the executable..."
& (Join-Path $AppDir "urh_debug.exe") autoclose
if ($LASTEXITCODE -ne 0) { Warn "'urh_debug.exe autoclose' returned $LASTEXITCODE; check the output above." }

# ------------------------------------------------------------------- decoders
if ($DecodersDir -and (Test-Path $DecodersDir)) {
    Info "Bundling decoders from $DecodersDir..."
    $DecDest = Join-Path $AppDir "decoders"
    if (Test-Path $DecDest) { Remove-Item -Recurse -Force $DecDest }
    Copy-Item -Recurse -Path $DecodersDir -Destination $DecDest
    Copy-Item (Join-Path $PSScriptRoot "install-decoders.ps1") $DecDest -Force
    Copy-Item (Join-Path $PSScriptRoot "install-decoders.bat") $DecDest -Force
    Get-ChildItem -Recurse -File $DecDest | ForEach-Object { Write-Host "      + $($_.FullName.Substring($DecDest.Length + 1))" }
} elseif ($DecodersDir) {
    Warn "${DecodersDir} does not exist: building without decoders."
}

$Version = (& $Py "src\urh\version.py").Trim()
$Dist    = Join-Path $Src "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
Get-ChildItem -Path $Dist -File -Filter "URH-NG-*" | Remove-Item -Force   # previous results

$Portable = Join-Path $Dist "URH-NG-$Version-win-x64-portable.zip"
Info "Creating the portable version: $Portable"
Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $Portable

# --------------------------------------------------------------------------- 5
if (-not $NoInstaller) {
    $Iscc = Find-Iscc
    if ($Iscc) {
        Info "Building the installer with Inno Setup..."
        Run $Iscc @("/dMyAppVersion=$Version", "/dArch=x64", "data\inno.iss")
    } else {
        Warn "Inno Setup not found: skipping the installer (the portable version is ready)."
    }
}

# --------------------------------------------------------------------------- done
Write-Host ""
Info "Build finished. Version: $Version"
Write-Host "   Program folder : $AppDir  (urh.exe)"
Write-Host "   Output files   : $Dist"
Get-ChildItem $Dist | ForEach-Object { Write-Host "      - $($_.Name)" }
Write-Host ""
Write-Host "   To use USB SDRs (HackRF, RTL-SDR...) install the WinUSB driver with Zadig: https://zadig.akeo.ie"
