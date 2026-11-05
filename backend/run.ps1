<#
.SYNOPSIS
    Run the MedGent CLI reliably, independent of the editable-install .pth.

.DESCRIPTION
    CPython on Windows reads editable-install `.pth` files using the system
    code page rather than UTF-8. When the install path contains non-ASCII
    characters (e.g. C:\Users\Usuário), the `.pth` is mojibake-corrupted and
    `python -m medgent` fails with `No module named 'medgent'`.

    This wrapper sidesteps that entirely by putting the source tree on
    PYTHONPATH (the same mechanism pytest already uses) before invoking the CLI
    through `uv run`, so the package is always importable regardless of the
    path's encoding.

.EXAMPLE
    ./run.ps1 "efficacy of metformin for type 2 diabetes"

.EXAMPLE
    ./run.ps1 "SGLT2 inhibitors in heart failure" --max-iterations 2 --model llama3.2:3b

.NOTES
    Run from the `backend/` directory. All arguments are forwarded verbatim to
    the `medgent` CLI (see `python -m medgent --help`).
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$ErrorActionPreference = "Stop"

# Resolve to this script's own directory so it works regardless of the caller's
# current location, then point PYTHONPATH at the package source.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $scriptDir "src"

uv run python -m medgent @ForwardArgs
exit $LASTEXITCODE
