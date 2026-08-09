# Initiate Research Lane plan for Grok
param(
  [string]$Cycle = "",
  [string]$Focus = ""
)
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
$args = @("scripts/multi_llm/initiate_plan.py", "--model", "grok")
if ($Cycle) { $args += @("--cycle", $Cycle) }
if ($Focus) { $args += @("--focus", $Focus) }
$env:PYTHONPATH = "src"
python @args
