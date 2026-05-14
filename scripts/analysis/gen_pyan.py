import glob, subprocess, sys, os

files = [f for f in glob.glob('**/*.py', recursive=True)
         if not any(x in f for x in ['Archieve','Backup','FuturePhaseConfig','bitnet_parity','venv','.claude'])
         and f.endswith('.py') and f != 'python_runner.py']

print(f"Total files: {len(files)}", flush=True)

# Try using pyan Python API directly to get full traceback
try:
    import pyan
    # Try pyan.create_callgraph or similar
    print("pyan version:", pyan.__version__ if hasattr(pyan, '__version__') else 'unknown', flush=True)
except Exception as e:
    print("pyan import error:", e, flush=True)

# Run with full stderr captured to a file
result = subprocess.run(
    ['pyan3'] + files + ['--dot', '--file', 'pyan_call_flow.dot'],
    capture_output=True, text=True, timeout=120
)
print(f"RC: {result.returncode}", flush=True)

with open('pyan_err.txt', 'w') as f:
    f.write(result.stderr)
    f.write('\n\nSTDOUT:\n')
    f.write(result.stdout)

print(f"Error written to pyan_err.txt ({len(result.stderr)} chars)", flush=True)
print("Last 500 chars of stderr:", result.stderr[-500:] if result.stderr else '(none)', flush=True)