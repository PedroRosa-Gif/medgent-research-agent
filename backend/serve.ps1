<#
.SYNOPSIS
    Run the MedGent HTTP API (FastAPI + SSE) reliably on Windows.

.DESCRIPTION
    CPython on Windows reads editable-install `.pth` files using the system code
    page rather than UTF-8. When the install path contains non-ASCII characters
    (e.g. C:\Users\Usuário), the `.pth` is mojibake-corrupted and importing
    `medgent` via `-m` fails with `No module named 'medgent'`.

    This wrapper sidesteps that by putting the source tree on PYTHONPATH (the same
    mechanism pytest and run.ps1 use) before launching uvicorn through `uv run`,
    so the package is always importable regardless of the path's encoding. uvicorn
    imports the app via the `--factory` form of `create_app`.

    A real research run needs the LLM provider up (default local Ollama):
        docker compose up -d
        docker compose logs -f ollama-init   # wait for the model pull to finish

.PARAMETER ApiHost
    Interface to bind (default: 127.0.0.1).

.PARAMETER Port
    Port to bind (default: 8000).

.PARAMETER Reload
    Enable uvicorn autoreload (development).

.EXAMPLE
    ./serve.ps1

.EXAMPLE
    ./serve.ps1 -ApiHost 0.0.0.0 -Port 8080 -Reload

.NOTES
    Run from the `backend/` directory.
#>
[CmdletBinding()]
param(
    [string]$ApiHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

# Resolve to this script's own directory so it works regardless of the caller's
# current location, then point PYTHONPATH at the package source.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $scriptDir "src"

$uvicornArgs = @(
    "medgent.adapters.driving.api.app:create_app",
    "--factory",
    "--host", $ApiHost,
    "--port", $Port
)
if ($Reload) {
    $uvicornArgs += "--reload"
}

uv run uvicorn @uvicornArgs
exit $LASTEXITCODE
