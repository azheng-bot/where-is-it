[CmdletBinding()]
param(
    [ValidateSet("api", "vision", "florence", "grounding", "sam", "embedding", "asr")]
    [string]$Service = "florence",
    [ValidateRange(1, 65535)]
    [int]$Port = 0,
    [string]$CloudflaredPath = (Join-Path $PSScriptRoot "..\.tools\cloudflared.exe")
)

$servicePorts = @{
    api       = 8000
    vision    = 8001
    florence  = 8002
    grounding = 8003
    sam       = 8004
    embedding = 8005
    asr       = 8006
}

$targetPort = if ($Port) { $Port } else { $servicePorts[$Service] }
$listener = Get-NetTCPConnection -State Listen -LocalPort $targetPort -ErrorAction SilentlyContinue
if (-not $listener) {
    throw "The local $Service service is not listening on 127.0.0.1:$targetPort. Start it first (for example: pnpm dev:models)."
}

if (-not (Test-Path -LiteralPath $CloudflaredPath)) {
    $toolsDirectory = Split-Path -Parent $CloudflaredPath
    New-Item -ItemType Directory -Force -Path $toolsDirectory | Out-Null
    Write-Host "Downloading the Cloudflare Tunnel client..."
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $CloudflaredPath
}

Write-Host "Creating a temporary HTTPS tunnel to local $Service service (127.0.0.1:$targetPort)..."
Write-Host "Give the displayed https://*.trycloudflare.com URL to the GPU service. Press Ctrl+C to close it."
& $CloudflaredPath tunnel --url "http://127.0.0.1:$targetPort"