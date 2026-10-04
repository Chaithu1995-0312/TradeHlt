"""
codebase_wiring_analysis.py
===========================
Analyze graph.dot (module import graph) to extract architecture insights:
- Dependency statistics per package
- Cyclic dependency detection
- Module centrality (most depended-on modules)
- Per-flow isolation metrics
- Critical import paths

Outputs:
  analysis_results.json  — structured data for visualization
  analysis_summary.txt   — human-readable summary
"""

import json
import re
from pathlib import Path
from collections import defaultdict, deque


def parse_dot(dot_path: Path) -> dict:
    """Parse graph.dot and extract nodes/edges."""
    content = dot_path.read_text(encoding='utf-8')

    nodes = set()
    edges = []

    # Parse nodes: "module.name"; or "module.name" [attributes];
    for match in re.finditer(r'"([^"]+)"\s*(?:\[[^\]]*\])?\s*;', content):
        nodes.add(match.group(1))

    # Parse edges: "src" -> "dst";
    for match in re.finditer(r'"([^"]+)"\s*->\s*"([^"]+)"\s*;', content):
        src, dst = match.group(1), match.group(2)
        edges.append((src, dst))

    return {'nodes': nodes, 'edges': edges}


def analyze_dependencies(nodes: set, edges: list) -> dict:
    """Compute dependency statistics."""
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)

    for src, dst in edges:
        out_degree[src] += 1
        in_degree[dst] += 1

    return {
        'in_degree': dict(in_degree),
        'out_degree': dict(out_degree),
        'total_modules': len(nodes),
        'total_edges': len(edges),
    }


def find_cycles(edges: list) -> list:
    """Detect circular dependencies (simplified via DFS)."""
    from collections import defaultdict

    graph = defaultdict(list)
    for src, dst in edges:
        graph[src].append(dst)

    cycles = []

    def dfs(node, path, visited):
        if node in path:
            # Found cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        for neighbor in graph[node]:
            dfs(neighbor, path + [node], visited.copy())

    # Make a copy of nodes before iterating
    for node in list(graph.keys()):
        dfs(node, [], set())

    # Deduplicate cycles
    unique_cycles = []
    for cycle in cycles:
        normalized = tuple(sorted(set(cycle)))
        if normalized not in [tuple(sorted(set(c))) for c in unique_cycles]:
            unique_cycles.append(cycle)

    return unique_cycles[:20]  # Limit to first 20


def analyze_per_package(nodes: set) -> dict:
    """Count modules per package."""
    packages = defaultdict(list)
    for node in nodes:
        pkg = node.split('.')[0]
        packages[pkg].append(node)

    return {pkg: {'count': len(mods), 'modules': sorted(mods)}
            for pkg, mods in sorted(packages.items())}


def find_critical_modules(in_degree: dict, out_degree: dict) -> dict:
    """Identify bottleneck modules (high in/out degree)."""
    most_depended_on = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:15]
    most_dependent = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        'most_depended_on': most_depended_on,
        'most_dependent': most_dependent,
    }


def analyze_flow_graph(flow_path: Path) -> dict:
    """Analyze a single flow's induced subgraph."""
    if not flow_path.exists():
        return None

    data = parse_dot(flow_path)
    nodes = data['nodes']
    edges = data['edges']

    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    boundary_edges = 0

    for src, dst in edges:
        if src in nodes:
            out_degree[src] += 1
        if dst in nodes:
            in_degree[dst] += 1
        # Count boundary edges (one endpoint outside flow)
        if (src in nodes) != (dst in nodes):
            boundary_edges += 1

    internal_edges = len(edges) - boundary_edges

    return {
        'modules': len(nodes),
        'internal_edges': internal_edges,
        'boundary_edges': boundary_edges,
        'total_edges': len(edges),
        'isolation_score': internal_edges / max(len(edges), 1),  # 1.0 = fully isolated
    }


def main():
    repo_root = Path(__file__).resolve().parents[2]
    graph_path = repo_root / 'graph.dot'
    flow_graphs_dir = repo_root / 'flow_graphs'

    # Parse main graph
    print("Parsing graph.dot...", end=' ', flush=True)
    graph_data = parse_dot(graph_path)
    print(f"OK ({len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges)")

    # Analyze
    print("Analyzing dependencies...", end=' ', flush=True)
    deps = analyze_dependencies(graph_data['nodes'], graph_data['edges'])
    print("OK")

    print("Finding cycles...", end=' ', flush=True)
    cycles = find_cycles(graph_data['edges'])
    print(f"OK ({len(cycles)} cycles found)")

    print("Per-package analysis...", end=' ', flush=True)
    packages = analyze_per_package(graph_data['nodes'])
    print(f"OK ({len(packages)} packages)")

    print("Critical modules...", end=' ', flush=True)
    critical = find_critical_modules(deps['in_degree'], deps['out_degree'])
    print("OK")

    # Per-flow analysis
    print("Per-flow analysis...", end=' ', flush=True)
    flows = {}
    for flow_path in sorted(flow_graphs_dir.glob('*.dot')):
        flow_name = flow_path.stem
        flows[flow_name] = analyze_flow_graph(flow_path)
    print(f"OK ({len(flows)} flows)")

    # Compile results
    results = {
        'summary': {
            'total_modules': deps['total_modules'],
            'total_edges': deps['total_edges'],
            'circular_dependencies': len(cycles),
            'packages': len(packages),
        },
        'packages': packages,
        'critical_modules': {
            'most_depended_on': critical['most_depended_on'],
            'most_dependent': critical['most_dependent'],
        },
        'cycles': cycles[:10],  # Limit output
        'flows': flows,
    }

    # Write JSON
    output_json = repo_root / 'analysis_results.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {output_json}")

    # Write summary
    output_txt = repo_root / 'analysis_summary.txt'
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("CODEBASE WIRING ANALYSIS\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Total Modules: {deps['total_modules']}\n")
        f.write(f"Total Dependencies: {deps['total_edges']}\n")
        f.write(f"Packages: {len(packages)}\n")
        f.write(f"Circular Dependencies: {len(cycles)}\n\n")

        f.write("TOP PACKAGES (by module count):\n")
        f.write("-" * 60 + "\n")
        for pkg, data in sorted(packages.items(), key=lambda x: x[1]['count'], reverse=True)[:10]:
            f.write(f"  {pkg:20s} {data['count']:3d} modules\n")

        f.write("\nTOP DEPENDED-ON MODULES (bottlenecks):\n")
        f.write("-" * 60 + "\n")
        for mod, count in critical['most_depended_on'][:10]:
            f.write(f"  {mod:50s} {count:3d} in-edges\n")

        f.write("\nTOP DEPENDENT MODULES (exporters):\n")
        f.write("-" * 60 + "\n")
        for mod, count in critical['most_dependent'][:10]:
            f.write(f"  {mod:50s} {count:3d} out-edges\n")

        f.write("\nPER-FLOW ISOLATION:\n")
        f.write("-" * 60 + "\n")
        for flow_name in sorted(flows.keys()):
            flow_data = flows[flow_name]
            if flow_data:
                f.write(f"  {flow_name:15s} {flow_data['modules']:2d} mods, "
                        f"{flow_data['internal_edges']:2d} internal, "
                        f"{flow_data['boundary_edges']:2d} boundary, "
                        f"isolation={flow_data['isolation_score']:.2f}\n")

        if cycles:
            f.write("\nCIRCULAR DEPENDENCIES (first 5):\n")
            f.write("-" * 60 + "\n")
            for i, cycle in enumerate(cycles[:5], 1):
                f.write(f"  Cycle {i}: {' -> '.join(cycle[:3])}...\n")

    print(f"Wrote {output_txt}")


if __name__ == '__main__':
    main()
