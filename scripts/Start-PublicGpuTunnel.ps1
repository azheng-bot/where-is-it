[CmdletBinding()]
param(
    [ValidateSet("api", "vision")]
    [string]$Service = "api",
    [ValidateRange(1, 65535)]
    [int]$Port = 0,
    [string]$CloudflaredPath = (Join-Path $PSScriptRoot "..\.tools\cloudflared.exe")
)

$servicePorts = @{ api = 8000; vision = 8001 }
$targetPort = if ($Port) { $Port } else { $servicePorts[$Service] }
$listener = Get-NetTCPConnection -State Listen -LocalPort $targetPort -ErrorAction SilentlyContinue
if (-not $listener) {
    throw "The local $Service service is not listening on 127.0.0.1:$targetPort. Start the GPU package first."
}

if (-not (Test-Path -LiteralPath $CloudflaredPath)) {
    $toolsDirectory = Split-Path -Parent $CloudflaredPath
    New-Item -ItemType Directory -Force -Path $toolsDirectory | Out-Null
    Write-Host "Downloading the Cloudflare Tunnel client..."
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $CloudflaredPath
}

Write-Host "Creating a temporary HTTPS tunnel to the GPU $Service entry point (127.0.0.1:$targetPort)..."
Write-Host "Press Ctrl+C to close it. Do not tunnel private model or ASR ports."
& $CloudflaredPath tunnel --url "http://127.0.0.1:$targetPort"