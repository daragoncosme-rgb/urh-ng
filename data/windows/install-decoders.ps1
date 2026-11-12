# =============================================================================
#  Install the decoders bundled with URH-NG into %APPDATA%\urh
# -----------------------------------------------------------------------------
#  - Copies the external decoder programs (windows-x64\*.exe) to
#    %APPDATA%\urh\decoders
#  - Backs up %APPDATA%\urh\decodings.txt
#  - Adds the missing decodings and rewrites the entries of the bundled
#    external decoders with the "d" (decode) and "e" (encode) arguments
#    they need. Your other decodings are kept unchanged.
#  URH and URH-NG read the same decodings.txt, so this works for both.
#  Safe to run several times. Close URH before running it.
#
#  Usage: double-click install-decoders.bat   (-Silent: do not wait for a key)
#  The URH-NG installer runs it automatically.
# =============================================================================
param([switch]$Silent)
$ErrorActionPreference = 'Stop'

function Done($code) {
    if (-not $Silent) { Write-Host ""; Read-Host "Press Enter to close" | Out-Null }
    exit $code
}

try {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $conf = Join-Path $env:APPDATA 'urh'
    $dest = Join-Path $conf 'decoders'

    if ($dest -match "[,;']") {
        Write-Host "Your user path contains , ; or ' and URH cannot use it in decodings.txt: $dest"
        Done 1
    }

    # Name shown in URH for each external program
    $labels = [ordered]@{
        'homematic_complete'     = 'HomeMatic (complete: whitening + CRC)'
        'homematic'              = 'HomeMatic (cipher only)'
        'enocean_switchtelegram' = 'EnOcean Switch Telegram'
    }

    # 1. Copy the programs
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $exes = @(Get-ChildItem -Path (Join-Path $here 'windows-x64') -Filter '*.exe' -ErrorAction SilentlyContinue)
    foreach ($e in $exes) {
        $target = Join-Path $dest $e.Name
        Copy-Item $e.FullName $target -Force
        Unblock-File $target -ErrorAction SilentlyContinue
        if (-not $labels.Contains($e.BaseName)) { $labels[$e.BaseName] = $e.BaseName }
    }
    Write-Host "$($exes.Count) decoder programs copied to $dest"

    # 2. Read the current decodings.txt (with a backup)
    $file = Join-Path $conf 'decodings.txt'
    $enc  = [System.Text.Encoding]::Default   # URH reads it with the local code page
    $existing = @()
    if (Test-Path $file) {
        Copy-Item $file "$file.bak.$(Get-Date -Format yyyyMMddHHmmss)"
        $existing = @([System.IO.File]::ReadAllLines($file, $enc) | Where-Object { $_.Trim() -ne '' })
    }
    function Name-Of($line) { (($line -split ',')[0]).Trim().Trim("'") }

    # 3. Lines of the external decoders, with the right syntax
    $extLines = @()
    foreach ($e in $exes) {
        $p = Join-Path $dest $e.Name
        $extLines += "'$($labels[$e.BaseName])', 'External Program', '`"$p`" d;`"$p`" e', "
    }
    $extNames = $extLines | ForEach-Object { Name-Of $_ }
    # Names used by older versions of this package, replaced by the ones above
    $oldNames = @('HomeMatic (completo: whitening + CRC)', 'HomeMatic (solo cifrado)')

    # 4. Bundled built-in decodings
    $prims = @()
    $primFile = Join-Path $here 'decodings.txt'
    if (Test-Path $primFile) {
        $prims = @([System.IO.File]::ReadAllLines($primFile, $enc) | Where-Object { $_.Trim() -ne '' })
    }

    # 5. Merge: keep your decodings, replace the bundled external ones
    $replace = @($extNames) + $oldNames
    $kept    = @($existing | Where-Object { $replace -notcontains (Name-Of $_) })
    $names   = @($kept | ForEach-Object { Name-Of $_ })
    $addPrim = @($prims | Where-Object { $names -notcontains (Name-Of $_) })
    $all     = @($kept) + $addPrim + $extLines
    [System.IO.File]::WriteAllLines($file, [string[]]$all, $enc)

    $replaced = @($existing | Where-Object { $replace -contains (Name-Of $_) }).Count
    Write-Host "$($addPrim.Count) built-in decodings added, $($extLines.Count) external decoders installed ($replaced replaced) in $file"

    # 6. Quick test
    $probe = Join-Path $dest 'enocean_switchtelegram.exe'
    if (Test-Path $probe) {
        & $probe d 1010 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host "Test OK." } else { Write-Host "Warning: the test returned $LASTEXITCODE." }
    }
    Write-Host "Open URH-NG: they are in the Analysis tab and in Edit -> Decoding."
    Done 0
} catch {
    Write-Host "Error: $_"
    Done 1
}
