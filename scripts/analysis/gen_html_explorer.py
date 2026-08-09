#!/usr/bin/env python3
"""
gen_html_explorer.py
====================
Generate an interactive HTML explorer for the codebase wiring analysis.

Reads analysis_results.json and graph.dot, then generates a self-contained
HTML page with embedded data and visualization capabilities.

Usage:
  python scripts/analysis/gen_html_explorer.py
"""

import json
import re
from pathlib import Path


def load_graph_data():
    """Load graph.dot and extract nodes/edges."""
    graph_path = Path("graph.dot")
    content = graph_path.read_text(encoding='utf-8')

    nodes = set()
    edges = []

    for match in re.finditer(r'"([^"]+)"\s*(?:\[[^\]]*\])?\s*;', content):
        nodes.add(match.group(1))

    for match in re.finditer(r'"([^"]+)"\s*->\s*"([^"]+)"\s*;', content):
        src, dst = match.group(1), match.group(2)
        if src in nodes and dst in nodes:
            edges.append((src, dst))

    # Organize by package
    packages = {}
    for node in nodes:
        pkg = node.split('.')[0]
        if pkg not in packages:
            packages[pkg] = []
        packages[pkg].append(node)

    return {
        'nodes': sorted(nodes),
        'edges': edges,
        'packages': {k: sorted(v) for k, v in sorted(packages.items())},
    }


def load_analysis():
    """Load analysis_results.json."""
    with open('analysis_results.json', encoding='utf-8') as f:
        return json.load(f)


def generate_html(graph_data, analysis):
    """Generate interactive HTML."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tradelatest Codebase Wiring Explorer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            height: 100vh;
            gap: 1px;
            background: #ddd;
        }
        .panel {
            background: white;
            overflow-y: auto;
            padding: 20px;
        }
        .panel h2 {
            margin-bottom: 15px;
            color: #222;
            font-size: 18px;
        }
        .panel h3 {
            margin-top: 15px;
            margin-bottom: 10px;
            color: #555;
            font-size: 14px;
            font-weight: 600;
        }
        .search-box {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
            border-bottom: 2px solid #eee;
        }
        .tab {
            padding: 10px 15px;
            cursor: pointer;
            border: none;
            background: none;
            color: #666;
            font-size: 14px;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }
        .tab.active {
            color: #0066cc;
            border-bottom-color: #0066cc;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .module-list {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .module-item {
            padding: 8px;
            background: #f9f9f9;
            border: 1px solid #eee;
            border-radius: 3px;
            cursor: pointer;
            font-size: 13px;
            font-family: 'Monaco', 'Courier', monospace;
            transition: all 0.15s;
        }
        .module-item:hover {
            background: #e3f2fd;
            border-color: #0066cc;
        }
        .module-item.selected {
            background: #0066cc;
            color: white;
            border-color: #0066cc;
        }
        .detail-section {
            margin-bottom: 20px;
        }
        .detail-section h4 {
            margin-bottom: 10px;
            color: #333;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .edge-list {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .edge-item {
            padding: 5px;
            font-size: 12px;
            font-family: 'Monaco', 'Courier', monospace;
            background: #f0f0f0;
            border-radius: 2px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }
        .stat-card {
            background: #f9f9f9;
            padding: 12px;
            border-radius: 4px;
            border: 1px solid #eee;
        }
        .stat-card .value {
            font-size: 20px;
            font-weight: bold;
            color: #0066cc;
        }
        .stat-card .label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .package-badge {
            display: inline-block;
            padding: 2px 6px;
            background: #e3f2fd;
            color: #0066cc;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 500;
            margin-right: 5px;
            margin-bottom: 5px;
        }
        .warning-badge {
            display: inline-block;
            padding: 4px 8px;
            background: #fff3e0;
            color: #e65100;
            border-radius: 3px;
            font-size: 12px;
            font-weight: 500;
        }
        .table {
            width: 100%;
            font-size: 12px;
            border-collapse: collapse;
        }
        .table th {
            text-align: left;
            padding: 8px;
            border-bottom: 2px solid #ddd;
            font-weight: 600;
        }
        .table td {
            padding: 8px;
            border-bottom: 1px solid #eee;
        }
        .table tr:hover {
            background: #f9f9f9;
        }
        .header {
            background: #0066cc;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 {
            font-size: 20px;
            margin-bottom: 5px;
        }
        .header p {
            font-size: 13px;
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Tradelatest Codebase Wiring Explorer</h1>
        <p>351 modules | 696 dependencies | 36 packages</p>
    </div>

    <div class="container">
        <!-- LEFT PANEL: Module Explorer -->
        <div class="panel">
            <h2>Module Explorer</h2>

            <div class="tabs">
                <button class="tab active" data-tab="search">Search</button>
                <button class="tab" data-tab="packages">Packages</button>
                <button class="tab" data-tab="bottlenecks">Bottlenecks</button>
            </div>

            <!-- Search Tab -->
            <div id="search" class="tab-content active">
                <input type="text" class="search-box" id="searchInput" placeholder="Search modules...">
                <div class="module-list" id="searchResults"></div>
            </div>

            <!-- Packages Tab -->
            <div id="packages" class="tab-content">
                <div id="packagesList"></div>
            </div>

            <!-- Bottlenecks Tab -->
            <div id="bottlenecks" class="tab-content">
                <h3>Most Depended-On Modules</h3>
                <div class="module-list" id="bottlenecksList"></div>
            </div>
        </div>

        <!-- RIGHT PANEL: Module Details -->
        <div class="panel">
            <h2>Module Details</h2>
            <div id="detailsContent">
                <p style="color: #999;">Select a module to view details...</p>
            </div>
        </div>
    </div>

    <script>
        // Embedded data
        const graphData = """ + json.dumps(graph_data) + """;
        const analysisData = """ + json.dumps(analysis) + """;

        // Build lookup structures
        const modules = new Set(graphData.nodes);
        const edgesMap = {};
        const reverseEdgesMap = {};

        graphData.edges.forEach(([src, dst]) => {
            if (!edgesMap[src]) edgesMap[src] = [];
            if (!reverseEdgesMap[dst]) reverseEdgesMap[dst] = [];
            edgesMap[src].push(dst);
            reverseEdgesMap[dst].push(src);
        });

        // Initialize UI
        function init() {
            populateSearchResults();
            populatePackages();
            populateBottlenecks();
            setupEventListeners();
        }

        function setupEventListeners() {
            // Tab switching
            document.querySelectorAll('.tab').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const tabName = e.target.dataset.tab;
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    e.target.classList.add('active');
                    document.getElementById(tabName).classList.add('active');
                });
            });

            // Search input
            document.getElementById('searchInput').addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                populateSearchResults(query);
            });
        }

        function populateSearchResults(query = '') {
            const results = graphData.nodes.filter(m => m.toLowerCase().includes(query));
            const html = results.map(m => `
                <div class="module-item" onclick="showModuleDetails('${m}')">${m}</div>
            `).join('');
            document.getElementById('searchResults').innerHTML = html || '<p style="color: #999; padding: 10px;">No results</p>';
        }

        function populatePackages() {
            const html = Object.entries(graphData.packages).map(([pkg, mods]) => `
                <div style="margin-bottom: 15px;">
                    <h4 style="color: #333; font-size: 12px; margin-bottom: 8px;">${pkg} (${mods.length})</h4>
                    <div class="module-list">
                        ${mods.slice(0, 5).map(m => `
                            <div class="module-item" onclick="showModuleDetails('${m}')">${m}</div>
                        `).join('')}
                        ${mods.length > 5 ? `<div style="padding: 5px; color: #999; font-size: 12px;">... and ${mods.length - 5} more</div>` : ''}
                    </div>
                </div>
            `).join('');
            document.getElementById('packagesList').innerHTML = html;
        }

        function populateBottlenecks() {
            const top = analysisData.critical_modules.most_depended_on.slice(0, 10);
            const html = top.map(([mod, count]) => `
                <div class="module-item" onclick="showModuleDetails('${mod}')">
                    <strong>${mod}</strong> <span style="float: right; color: #999;">${count}</span>
                </div>
            `).join('');
            document.getElementById('bottlenecksList').innerHTML = html;
        }

        function showModuleDetails(moduleName) {
            const deps = edgesMap[moduleName] || [];
            const dependents = reverseEdgesMap[moduleName] || [];
            const pkg = moduleName.split('.')[0];

            const html = `
                <div class="detail-section">
                    <h3 style="font-size: 16px; margin-bottom: 10px;">
                        ${moduleName}
                        <span class="package-badge">${pkg}</span>
                    </h3>
                </div>

                <div class="detail-section">
                    <h4>Dependencies (${deps.length})</h4>
                    ${deps.length === 0 ? '<p style="color: #999; font-size: 12px;">No dependencies</p>' : `
                        <div class="edge-list">
                            ${deps.slice(0, 15).map(d => `
                                <div class="edge-item">-> ${d}</div>
                            `).join('')}
                            ${deps.length > 15 ? `<div style="padding: 5px; color: #999; font-size: 12px;">... and ${deps.length - 15} more</div>` : ''}
                        </div>
                    `}
                </div>

                <div class="detail-section">
                    <h4>Depended On By (${dependents.length})</h4>
                    ${dependents.length === 0 ? '<p style="color: #999; font-size: 12px;">No dependents</p>' : `
                        <div class="edge-list">
                            ${dependents.slice(0, 15).map(d => `
                                <div class="edge-item"><- ${d}</div>
                            `).join('')}
                            ${dependents.length > 15 ? `<div style="padding: 5px; color: #999; font-size: 12px;">... and ${dependents.length - 15} more</div>` : ''}
                        </div>
                    `}
                </div>
            `;
            document.getElementById('detailsContent').innerHTML = html;
        }

        // Initialize on load
        init();
    </script>
</body>
</html>
"""
    return html


def main():
    print("Loading graph data...", end=" ", flush=True)
    graph_data = load_graph_data()
    print(f"OK ({len(graph_data['nodes'])} modules)")

    print("Loading analysis...", end=" ", flush=True)
    analysis = load_analysis()
    print("OK")

    print("Generating HTML...", end=" ", flush=True)
    html = generate_html(graph_data, analysis)
    print("OK")

    output_path = Path("codebase_explorer.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Wrote {output_path} ({len(html)} bytes)")
    print(f"\nOpen in browser: {output_path.absolute()}")


if __name__ == '__main__':
    main()
