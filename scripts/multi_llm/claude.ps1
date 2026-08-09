param([string]$Cycle = "", [string]$Focus = "")
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
$a = @("scripts/multi_llm/initiate_plan.py", "--model", "claude")
if ($Cycle) { $a += @("--cycle", $Cycle) }
if ($Focus) { $a += @("--focus", $Focus) }
$env:PYTHONPATH = "src"
python @a
