#!/usr/bin/env python3
"""
graph_query.py
==============
Interactive query tool for the codebase dependency graph (graph.dot).

Usage:
  python graph_query.py --module core.engine_runner
  python graph_query.py --downstream config_layer.production_config
  python graph_query.py --path core.engine_runner features.feature_pipeline
  python graph_query.py --flow runtime
  python graph_query.py --cycles
  python graph_query.py --package core
  python graph_query.py --stats
"""

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path


class DependencyGraph:
    """Parse and query graph.dot."""

    def __init__(self, dot_path: Path):
        self.path = dot_path
        self.nodes = set()
        self.edges = []
        self.forward_edges = defaultdict(set)  # node -> [deps]
        self.reverse_edges = defaultdict(set)  # node <- [dependents]
        self.packages = defaultdict(set)
        self._parse()

    def _parse(self):
        """Parse graph.dot."""
        content = self.path.read_text(encoding='utf-8')

        # Parse nodes
        for match in re.finditer(r'"([^"]+)"\s*(?:\[[^\]]*\])?\s*;', content):
            node = match.group(1)
            self.nodes.add(node)
            # Track by package
            pkg = node.split('.')[0]
            self.packages[pkg].add(node)

        # Parse edges
        for match in re.finditer(r'"([^"]+)"\s*->\s*"([^"]+)"\s*;', content):
            src, dst = match.group(1), match.group(2)
            if src in self.nodes and dst in self.nodes:
                self.edges.append((src, dst))
                self.forward_edges[src].add(dst)
                self.reverse_edges[dst].add(src)

    def module_info(self, module: str):
        """Show all dependencies of a module."""
        if module not in self.nodes:
            return f"[ERROR] Module '{module}' not found"

        direct_deps = self.forward_edges[module]
        direct_dependents = self.reverse_edges[module]

        result = f"MODULE: {module}\n"
        result += "-" * 70 + "\n"

        if direct_deps:
            result += f"\nDEPENDENCIES ({len(direct_deps)}):\n"
            for dep in sorted(direct_deps):
                result += f"  -> {dep}\n"
        else:
            result += "\nNo direct dependencies\n"

        if direct_dependents:
            result += f"\nDEPENDED ON BY ({len(direct_dependents)}):\n"
            for dep in sorted(direct_dependents):
                result += f"  <- {dep}\n"
        else:
            result += "\nNo modules depend on this\n"

        return result

    def downstream(self, module: str) -> str:
        """Find all modules that depend on this (transitive)."""
        if module not in self.nodes:
            return f"[ERROR] Module '{module}' not found"

        # BFS to find all dependents
        visited = set()
        queue = deque(self.reverse_edges[module])

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            for dep in self.reverse_edges[node]:
                queue.append(dep)

        result = f"MODULES DEPENDING ON: {module}\n"
        result += "-" * 70 + "\n"
        result += f"\nTransitive dependents ({len(visited)}):\n"
        for node in sorted(visited):
            result += f"  <- {node}\n"

        return result

    def shortest_path(self, src: str, dst: str) -> str:
        """Find shortest import path from src to dst."""
        if src not in self.nodes:
            return f"[ERROR] Source '{src}' not found"
        if dst not in self.nodes:
            return f"[ERROR] Destination '{dst}' not found"

        # BFS
        visited = {src}
        queue = deque([(src, [src])])

        while queue:
            node, path = queue.popleft()

            if node == dst:
                result = f"SHORTEST PATH: {src} -> {dst}\n"
                result += "-" * 70 + "\n"
                result += f"\nPath length: {len(path) - 1}\n"
                for i, module in enumerate(path):
                    indent = "  " * i
                    result += f"{indent}-> {module}\n"
                return result

            for next_node in self.forward_edges[node]:
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, path + [next_node]))

        return f"[ERROR] No path found from {src} to {dst}"

    def package_info(self, package: str) -> str:
        """Show all modules in a package."""
        if package not in self.packages:
            return f"[ERROR] Package '{package}' not found"

        modules = sorted(self.packages[package])
        result = f"PACKAGE: {package}\n"
        result += "-" * 70 + "\n"
        result += f"\nModules ({len(modules)}):\n"
        for mod in modules:
            result += f"  * {mod}\n"

        return result

    def flow_info(self, flow_name: str) -> str:
        """Load and display a flow graph."""
        repo_root = self.path.parent
        flow_path = repo_root / "flow_graphs" / f"{flow_name}.dot"

        if not flow_path.exists():
            return f"[ERROR] Flow '{flow_name}' not found. Available: agent, control_plane, governance, research, runtime, telemetry, training"

        content = flow_path.read_text(encoding='utf-8')

        # Parse flow nodes/edges
        flow_nodes = set()
        for match in re.finditer(r'"([^"]+)"\s*(?:\[[^\]]*\])?\s*;', content):
            flow_nodes.add(match.group(1))

        flow_edges = []
        for match in re.finditer(r'"([^"]+)"\s*->\s*"([^"]+)"\s*;', content):
            flow_edges.append((match.group(1), match.group(2)))

        result = f"FLOW: {flow_name}\n"
        result += "-" * 70 + "\n"
        result += f"\nModules ({len(flow_nodes)}):\n"
        for node in sorted(flow_nodes):
            result += f"  * {node}\n"

        result += f"\nDependencies ({len(flow_edges)}):\n"
        for src, dst in sorted(flow_edges)[:20]:
            result += f"  {src} -> {dst}\n"
        if len(flow_edges) > 20:
            result += f"  ... and {len(flow_edges) - 20} more\n"

        return result

    def cycles(self) -> str:
        """Find circular dependencies."""
        cycles_list = []

        def dfs(node, path, visited):
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles_list.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            for neighbor in self.forward_edges[node]:
                dfs(neighbor, path + [node], visited.copy())

        for node in list(self.forward_edges.keys()):
            dfs(node, [], set())

        # Deduplicate
        unique = []
        for cycle in cycles_list:
            normalized = tuple(sorted(set(cycle)))
            if normalized not in [tuple(sorted(set(c))) for c in unique]:
                unique.append(cycle)

        result = f"CIRCULAR DEPENDENCIES\n"
        result += "-" * 70 + "\n"

        if not unique:
            result += "\n[OK] No cycles detected\n"
        else:
            result += f"\n[WARNING] Found {len(unique)} unique cycles:\n\n"
            for i, cycle in enumerate(unique[:10], 1):
                result += f"Cycle {i}:\n"
                for j, node in enumerate(cycle[:-1]):
                    result += f"  {node}\n"
                    result += f"    |\n"
                result += f"  {cycle[-1]}\n\n"

        return result

    def stats(self) -> str:
        """Overall statistics."""
        # Compute centrality
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)

        for src, dst in self.edges:
            in_degree[dst] += 1
            out_degree[src] += 1

        most_depended = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:5]
        most_dependent = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:5]

        result = "CODEBASE STATISTICS\n"
        result += "-" * 70 + "\n"
        result += f"\nModules: {len(self.nodes)}\n"
        result += f"Dependencies: {len(self.edges)}\n"
        result += f"Packages: {len(self.packages)}\n"

        result += f"\nTOP DEPENDED-ON (bottlenecks):\n"
        for mod, count in most_depended:
            result += f"  {mod:50s} {count:3d} in-edges\n"

        result += f"\nTOP DEPENDENT (exporters):\n"
        for mod, count in most_dependent:
            result += f"  {mod:50s} {count:3d} out-edges\n"

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Query the Tradelatest dependency graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("--module", help="Show dependencies of a module")
    parser.add_argument("--downstream", help="Show modules depending on this")
    parser.add_argument("--path", nargs=2, metavar=("FROM", "TO"), help="Shortest path between modules")
    parser.add_argument("--package", help="Show all modules in a package")
    parser.add_argument("--flow", help="Show a flow's topology")
    parser.add_argument("--cycles", action="store_true", help="Find circular dependencies")
    parser.add_argument("--stats", action="store_true", help="Show overall statistics")

    args = parser.parse_args()

    if not any([args.module, args.downstream, args.path, args.package, args.flow, args.cycles, args.stats]):
        parser.print_help()
        sys.exit(1)

    repo_root = Path(__file__).resolve().parents[2]
    graph_path = repo_root / "graph.dot"

    if not graph_path.exists():
        print(f"[ERROR] graph.dot not found at {graph_path}")
        sys.exit(1)

    graph = DependencyGraph(graph_path)

    if args.module:
        print(graph.module_info(args.module))
    elif args.downstream:
        print(graph.downstream(args.downstream))
    elif args.path:
        print(graph.shortest_path(args.path[0], args.path[1]))
    elif args.package:
        print(graph.package_info(args.package))
    elif args.flow:
        print(graph.flow_info(args.flow))
    elif args.cycles:
        print(graph.cycles())
    elif args.stats:
        print(graph.stats())


if __name__ == '__main__':
    main()
