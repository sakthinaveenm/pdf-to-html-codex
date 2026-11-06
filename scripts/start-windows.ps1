# Called by start-windows.cmd; works with Windows PowerShell 5.1 and PowerShell 7.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Refresh-ToolPath {
    $paths = @(
        "$env:USERPROFILE\.local\bin",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links",
        "$env:ProgramFiles\nodejs",
        "$env:ProgramFiles\Tesseract-OCR",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR",
        [Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [Environment]::GetEnvironmentVariable('Path', 'User'),
        $env:Path
    )
    $env:Path = ($paths | Where-Object { $_ }) -join ';'
}
function Install-WingetPackage([string] $Package) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'WinGet is missing. Install Microsoft App Installer from the Microsoft Store, then run this launcher again.'
    }
    Write-Host "Installing $Package (Windows may request administrator approval)..."
    & winget.exe install --id $Package --exact --force --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "WinGet installation failed for $Package (exit $LASTEXITCODE)." }
    Refresh-ToolPath
}
try {
    Refresh-ToolPath
    if (-not (Get-Command uv.exe -ErrorAction SilentlyContinue)) {
        Write-Host 'Installing uv from its official installer...'
        $installer = Invoke-WebRequest -UseBasicParsing 'https://astral.sh/uv/install.ps1'
        & ([scriptblock]::Create($installer.Content))
        Refresh-ToolPath
    }
    if (-not (Get-Command uv.exe -ErrorAction SilentlyContinue)) { throw 'uv installation did not produce a usable uv.exe.' }
    $needsNode = $true
    if ((Get-Command node.exe -ErrorAction SilentlyContinue) -and (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        & node.exe -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 24 ? 0 : 1)'
        $needsNode = $LASTEXITCODE -ne 0
    }
    if ($needsNode) { Install-WingetPackage 'OpenJS.NodeJS.LTS' }
    if (($args -notcontains '--skip-ocr') -and -not (Get-Command tesseract.exe -ErrorAction SilentlyContinue)) {
        Install-WingetPackage 'UB-Mannheim.TesseractOCR'
    }
    & uv.exe python install 3.11
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 installation failed.' }
    & uv.exe run --no-project --python 3.11 scripts/start.py @args
    exit $LASTEXITCODE
} catch {
    Write-Host "`nStartup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
