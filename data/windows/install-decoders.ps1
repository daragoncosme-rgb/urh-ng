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
#  The URH-NG installer runs it automatically for the user who installs it;
#  other Windows users can run it from URH-NG: Help -> Install decoders.
#  -SourceDir: folder with windows-x64\ and decodings.txt (default: this
#  script's folder).
# =============================================================================
param([switch]$Silent, [string]$SourceDir = "")
$ErrorActionPreference = 'Stop'

# URH stores decodings in a text file where , ; and ' are separators, and it
# reads the file with the system code page. If the user's folder contains any
# of those characters (or characters outside the code page), use the short
# 8.3 form of the path, which never contains them.
function Get-SafePath([string]$path) {
    $enc = [System.Text.Encoding]::Default
    $roundTrip = $enc.GetString($enc.GetBytes($path))
    if ($path -notmatch "[,;']" -and $roundTrip -eq $path) { return $path }
    try {
        $short = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($path).ShortPath
        if ($short -and $short -notmatch "[,;']") { return $short }
    } catch { }
    return $null
}

# Write to stdout without the host's line wrapping (Write-Host wraps long
# lines at 80 columns when started without a console, e.g. from URH-NG)
function Say([string]$m) { [Console]::Out.WriteLine($m) }

function Done($code) {
    if (-not $Silent) { Say ""; Read-Host "Press Enter to close" | Out-Null }
    exit $code
}

try {
    $here = if ($SourceDir) { $SourceDir } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $conf = Join-Path $env:APPDATA 'urh'
    $dest = Join-Path $conf 'decoders'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    # Path written into decodings.txt (the files are copied to $dest)
    $destForUrh = Get-SafePath $dest
    if (-not $destForUrh) {
        Say "URH cannot use this folder in decodings.txt (it contains , ; or ' and has no short 8.3 name): $dest"
        Done 1
    }

    # Name shown in URH for each external program
    $labels = [ordered]@{
        'homematic_complete'     = 'HomeMatic (complete: whitening + CRC)'
        'homematic'              = 'HomeMatic (cipher only)'
        'enocean_switchtelegram' = 'EnOcean Switch Telegram'
    }

    # 1. Copy the programs
    $exes = @(Get-ChildItem -LiteralPath (Join-Path $here 'windows-x64') -Filter '*.exe' -ErrorAction SilentlyContinue)
    foreach ($e in $exes) {
        $target = Join-Path $dest $e.Name
        Copy-Item -LiteralPath $e.FullName -Destination $target -Force
        Unblock-File -LiteralPath $target -ErrorAction SilentlyContinue
        if (-not $labels.Contains($e.BaseName)) { $labels[$e.BaseName] = $e.BaseName }
    }
    Say "$($exes.Count) decoder programs copied to $dest"

    # 2. Read the current decodings.txt (with a backup)
    $file = Join-Path $conf 'decodings.txt'
    $enc  = [System.Text.Encoding]::Default   # URH reads it with the local code page
    $existing = @()
    if (Test-Path -LiteralPath $file) {
        Copy-Item -LiteralPath $file -Destination "$file.bak.$(Get-Date -Format yyyyMMddHHmmss)"
        $existing = @([System.IO.File]::ReadAllLines($file, $enc) | Where-Object { $_.Trim() -ne '' })
    }
    function Name-Of($line) { (($line -split ',')[0]).Trim().Trim("'") }

    # 3. Lines of the external decoders, with the right syntax
    $extLines = @()
    foreach ($e in $exes) {
        $p = Join-Path $destForUrh $e.Name
        $extLines += "'$($labels[$e.BaseName])', 'External Program', '`"$p`" d;`"$p`" e', "
    }
    $extNames = $extLines | ForEach-Object { Name-Of $_ }
    # Names used by older versions of this package, replaced by the ones above
    $oldNames = @('HomeMatic (completo: whitening + CRC)', 'HomeMatic (solo cifrado)')

    # 4. Bundled built-in decodings
    $prims = @()
    $primFile = Join-Path $here 'decodings.txt'
    if (Test-Path -LiteralPath $primFile) {
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
    Say "$($addPrim.Count) built-in decodings added, $($extLines.Count) external decoders installed ($replaced replaced) in $file"

    # 6. Quick test
    $probe = Join-Path $dest 'enocean_switchtelegram.exe'
    if (Test-Path -LiteralPath $probe) {
        & $probe d 1010 | Out-Null
        if ($LASTEXITCODE -eq 0) { Say "Test OK." } else { Say "Warning: the test returned $LASTEXITCODE." }
    }
    Say "Open URH-NG: they are in the Analysis tab and in Edit -> Decoding."
    Done 0
} catch {
    Say "Error: $_"
    Done 1
}
