import json

# Load DAG layers
with open('docs/governance/feature_dag_layers-2026-07-12.json') as f:
    dag = json.load(f)

# Load certification ledger
ledger_lines = []
with open('docs/governance/feature_certification_ledger.jsonl') as f:
    for line in f:
        line = line.strip()
        if line:
            ledger_lines.append(json.loads(line))

# Build set of all DAG node identities
dag_node_names = set(n['name'] for n in dag['nodes'])
print(f'DAG_NODE_COUNT: {len(dag_node_names)}')

# Build latest disposition per identity from ledger
# The ledger is append-only; latest event for each identity determines current state
latest_disposition = {}  # identity -> latest event dict
for event in ledger_lines:
    name = event.get('feature_name')
    if name:
        latest_disposition[name] = event

ledger_identities = set(latest_disposition.keys())
print(f'LEDGER_IDENTITY_COUNT: {len(ledger_identities)}')

# Compare sets
missing_from_ledger = dag_node_names - ledger_identities
extra_in_ledger = ledger_identities - dag_node_names
print(f'MISSING_FROM_LEDGER: {sorted(missing_from_ledger)}')
print(f'EXTRA_IN_LEDGER: {sorted(extra_in_ledger)}')

# Check for conflicting terminal dispositions
print('\n=== Current dispositions per identity ===')
dup_terminal = {}
for name, event in sorted(latest_disposition.items()):
    state = event.get('frontier_state', 'UNKNOWN')
    print(f'  {name:30s} -> {state}')
    
# Recompute READY/BLOCKED frontier
# READY: all direct deps have PROMOTED_PRODUCTION
# BLOCKED: at least one dep NOT PROMOTED_PRODUCTION

print('\n=== DEPENDENCY DEPTHS (for frontier recomputation) ===')

# Build dep -> list of reverse dependents
dep_to_consumers = {}
for n in dag['nodes']:
    for dep in n.get('deps', []):
        if dep not in dep_to_consumers:
            dep_to_consumers[dep] = []
        dep_to_consumers[dep].append(n['name'])

ready = []
blocked = []
still_unknown = []

for n in dag['nodes']:
    name = n['name']
    state = latest_disposition.get(name, {}).get('frontier_state', 'SEEDED')
    
    if state == 'PROMOTED_PRODUCTION':
        continue  # Already terminal
    
    deps = n.get('deps', [])
    all_deps_promoted = True
    missing_dep = None
    for dep in deps:
        dep_state = latest_disposition.get(dep, {}).get('frontier_state', 'SEEDED')
        if dep_state != 'PROMOTED_PRODUCTION':
            all_deps_promoted = False
            missing_dep = dep
            break
    
    if all_deps_promoted:
        ready.append(name)
    else:
        blocked.append((name, missing_dep, dep_state))
    still_unknown.append(name)

print(f'\nRECOMPUTED_READY ({len(ready)}):')
for r in sorted(ready):
    print(f'  {r}')

print(f'\nRECOMPUTED_BLOCKED ({len(blocked)}):')
for name, dep, dep_state in sorted(blocked):
    print(f'  {name} BLOCKED on {dep} ({dep_state})')

print(f'\n=== TARGET: liquidity_pressure_score ===')
lps = [n for n in dag['nodes'] if n['name'] == 'liquidity_pressure_score'][0]
print(f'  Dependencies: {lps["deps"]}')
ld_dep = lps['deps'][0]
ld_state = latest_disposition.get(ld_dep, {}).get('frontier_state', 'UNKNOWN')
print(f'  {ld_dep} disposition: {ld_state}')
print(f'  liquidity_pressure_score READY: {ld_state == "PROMOTED_PRODUCTION"}')