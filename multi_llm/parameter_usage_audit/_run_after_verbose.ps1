$env:PYTHONPATH = 'D:\Tradelatest;D:\Tradelatest\src'
Set-Location 'D:\Tradelatest'
& 'D:\Tradelatest\.venv\Scripts\python.exe' -m pytest tests/ -v --tb=no --timeout=120 --timeout-method=thread --junitxml='D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_junit.xml' --continue-on-collection-errors 2>'D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_stderr.txt' | Out-File -FilePath 'D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER.txt' -Encoding utf8
"AFTER_EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Add-Content 'D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_status.txt'
& 'D:\Tradelatest\.venv\Scripts\python.exe' -c @'
import xml.etree.ElementTree as ET
from pathlib import Path
root = ET.parse(r"D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_junit.xml").getroot()
failed, passed = [], []
for tc in root.iter("testcase"):
    node = f"{tc.attrib.get(\"classname\",\"\")}::{tc.attrib.get(\"name\",\"\")}"
    if tc.find("failure") is not None or tc.find("error") is not None:
        failed.append(node)
    elif tc.find("skipped") is None:
        passed.append(node)
Path(r"D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_failed.txt").write_text("\n".join(sorted(failed))+"\n", encoding="utf-8")
Path(r"D:\Tradelatest\multi_llm\parameter_usage_audit\suite_AFTER_passed.txt").write_text("\n".join(sorted(passed))+"\n", encoding="utf-8")
print(f"AFTER failed={len(failed)} passed={len(passed)}")
'@
