import subprocess, sys, time, pathlib
root = pathlib.Path(r'D:\Tradelatest')
out = pathlib.Path(r'D:\Tradelatest\multi_llm\parameter_usage_audit\hang3_sampler_out')
cmd = [str(root/'.venv'/'Scripts'/'python.exe'), str(root/'scripts'/'analysis'/'blind_label_sample.py'),
       '--seed', '20260801', '--output-dir', str(out)]
t0 = time.time()
try:
    # wall 300s — distinguishes slow (~180s) vs hung
    r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=300)
    dt = time.time() - t0
    pathlib.Path(r'D:\Tradelatest\multi_llm\parameter_usage_audit\hang3_sampler_direct.txt').write_text(
        f'EXIT={r.returncode}\nELAPSED_SEC={dt:.1f}\nSTDOUT:\n{r.stdout[-2000:]}\nSTDERR:\n{r.stderr[-2000:]}\n',
        encoding='utf-8')
except subprocess.TimeoutExpired as e:
    dt = time.time() - t0
    pathlib.Path(r'D:\Tradelatest\multi_llm\parameter_usage_audit\hang3_sampler_direct.txt').write_text(
        f'HUNG_OR_SLOWER_THAN_300S\nELAPSED_SEC={dt:.1f}\n', encoding='utf-8')
    sys.exit(124)
