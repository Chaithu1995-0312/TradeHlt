from pathlib import Path
import subprocess, sys, re, time, os

root = Path(r'D:\Tradelatest')
audit = root / 'multi_llm' / 'parameter_usage_audit'
log = audit / 'triage_timeout30.txt'
status = audit / 'triage_status.txt'
py = root / '.venv' / 'Scripts' / 'python.exe'

cmd = [
    str(py), '-m', 'pytest', 'tests/',
    '-q', '--tb=no', '--no-header',
    '--timeout=30', '--timeout-method=thread',
    '-p', 'no:cacheprovider',
]
t0 = time.time()
env = os.environ.copy()
env['PYTHONPATH'] = str(root) + ';' + str(root / 'src')
status.write_text('TRIAGE_START\n', encoding='utf-8')
with log.open('w', encoding='utf-8', errors='replace') as out:
    out.write('TRIAGE_CMD ' + ' '.join(cmd) + '\n')
    out.flush()
    p = subprocess.run(cmd, cwd=str(root), env=env, stdout=out, stderr=subprocess.STDOUT)
dt = time.time() - t0
text = log.read_text(encoding='utf-8', errors='replace')

timeout_nodes = []
for line in text.splitlines():
    if re.search(r'Timeout|timed out|timeout exceeded', line, re.I):
        m = re.search(r'(tests/\S+::\S+)', line)
        if m:
            timeout_nodes.append(m.group(1).rstrip(':]'))
for m in re.finditer(r'^(FAILED|ERROR) (tests/\S+::\S+)', text, re.M):
    # keep only if timeout mentioned on same line or next patterns
    pass
# short summary: FAILED/ERROR lines that mention timeout
for line in text.splitlines():
    m = re.match(r'^(?:FAILED|ERROR) (tests/\S+::\S+)', line)
    if m and re.search(r'timeout', line, re.I):
        timeout_nodes.append(m.group(1))
# pytest-timeout often: "tests/...::test FAILED" then separate timeout message —
# also capture any node that appears with "+ Timeout +" style from -v; we used -q so rely on summary
# Fallback: all FAILED/ERROR from short summary for manual filter
failed_nodes = []
in_sum = False
for line in text.splitlines():
    if 'short test summary' in line.lower():
        in_sum = True
        continue
    if in_sum:
        m = re.match(r'^(FAILED|ERROR) (.+)$', line)
        if m:
            failed_nodes.append(m.group(2).strip())

uniq = sorted(set(timeout_nodes))
(audit / 'HANG_DESELECT_LIST.txt').write_text('\n'.join(uniq) + ('\n' if uniq else ''), encoding='utf-8')
(audit / 'triage_failed_or_error.txt').write_text('\n'.join(sorted(set(failed_nodes))) + '\n', encoding='utf-8')
status.write_text(
    f'TRIAGE_DONE exit={p.returncode} elapsed_sec={dt:.1f} timeout_nodes={len(uniq)} failed_or_error={len(set(failed_nodes))}\n',
    encoding='utf-8',
)
print(status.read_text(encoding='utf-8'))
print('TIMEOUT NODES:', len(uniq))
print('\n'.join(uniq[:50]))
