#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full graph connectivity analysis."""
import os, re, sys
from collections import defaultdict

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

VAULT = os.path.abspath(r"Q:\AI\kb")
SEP = os.sep

exclude_dirs = {'.git', '.obsidian', '.claude', '.claudian', '__pycache__',
                '.venv', '.superpowers', '.remember', '.github', '.env'}

# Collect files
all_files = []
for root, dirs, files in os.walk(VAULT):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for f in files:
        if f.endswith('.md'):
            all_files.append(os.path.join(root, f))

# basename -> list of rel paths
note_rel = defaultdict(list)
for fp in all_files:
    rel = os.path.relpath(fp, VAULT).replace(SEP, '/').replace('.md', '')
    base = os.path.splitext(os.path.basename(fp))[0]
    note_rel[base].append(rel)

# Build alias map
alias_to_rel = {}
for fp in all_files:
    rel = os.path.relpath(fp, VAULT).replace(SEP, '/').replace('.md', '')
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        continue
    fm = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if fm:
        for am in re.finditer(r'aliases:\s*\[(.*?)\]', fm.group(1)):
            for a in am.group(1).split(','):
                a = a.strip().strip('"').strip("'")
                if a:
                    alias_to_rel[a] = rel

# Build graph edges
link_pat = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
edges = defaultdict(set)
reverse = defaultdict(set)

def resolve_target(t):
    """Resolve a wikilink target to a rel path."""
    t = t.strip()
    if t.startswith('#'):
        return None
    t_base = os.path.basename(t.replace('/', SEP)).replace('.md', '')
    # Try alias first
    if t in alias_to_rel:
        return alias_to_rel[t]
    # Try basename
    if t_base in note_rel:
        return note_rel[t_base][0]
    # Try full path
    fpath = os.path.join(VAULT, t.replace('/', SEP) + '.md')
    if os.path.exists(fpath):
        return t
    return None

for fp in all_files:
    src_rel = os.path.relpath(fp, VAULT).replace(SEP, '/').replace('.md', '')
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        continue
    for m in link_pat.finditer(content):
        target = m.group(1).strip()
        tgt_rel = resolve_target(target)
        if tgt_rel and tgt_rel != src_rel:
            edges[src_rel].add(tgt_rel)
            reverse[tgt_rel].add(src_rel)

# Build undirected adjacency
adj = defaultdict(set)
for s, targets in edges.items():
    for t in targets:
        adj[s].add(t)
        adj[t].add(s)

# Connected components
visited = set()
components = []
for node in note_rel.values():
    for rel in node:
        if rel in visited:
            continue
        comp = []
        queue = [rel]
        while queue:
            n = queue.pop(0)
            if n in visited:
                continue
            visited.add(n)
            comp.append(n)
            for nb in adj.get(n, set()):
                if nb not in visited:
                    queue.append(nb)
        if comp:
            components.append(comp)

components.sort(key=len, reverse=True)

total_nodes = sum(len(v) for v in note_rel.values())
print(f"Total unique nodes: {total_nodes}")
print(f"Connected components: {len(components)}")
print()

# Component sizes
for i, comp in enumerate(components[:8]):
    pct = len(comp) / total_nodes * 100
    print(f"  Component {i+1}: {len(comp)} nodes ({pct:.1f}%)")
if len(components) > 8:
    rest = sum(len(c) for c in components[8:])
    print(f"  Components 9-{len(components)}: {rest} nodes total")

# Small clusters
print()
print("=== Small isolated clusters (2-15 nodes) ===")
for comp in components:
    if 2 <= len(comp) <= 15:
        print(f"  [{len(comp)} nodes]")
        for n in sorted(comp)[:8]:
            out = len(edges.get(n, set()))
            inn = len(reverse.get(n, set()))
            print(f"    {n}  (out={out}, in={inn})")
        if len(comp) > 8:
            print(f"    ... +{len(comp)-8} more")

# Single-node orphans (real knowledge)
print()
skip_prefixes = ('00-index/', 'copilot/', 'Excalidraw/', '.claudian/',
                 'test-data/', 'scripts/', '.claude/', '_archives/',
                 '_meta/', '_raw/', '.remember/', '.superpowers/')
skip_names = {'热点', '日志', '索引', 'README'}
real_orphans = []
for comp in components:
    if len(comp) == 1:
        n = comp[0]
        if any(n.startswith(p) for p in skip_prefixes):
            continue
        base = os.path.basename(n)
        if base in skip_names:
            continue
        real_orphans.append(n)

print(f"=== Real single-node orphans: {len(real_orphans)} ===")
for o in sorted(real_orphans):
    print(f"  {o}")

# Degree stats
print()
print("=== Lowest degree nodes (in main component, degree <= 2) ===")
main_comp = set(components[0]) if components else set()
low_degree = []
for rel_set in note_rel.values():
    for rel in rel_set:
        if rel in main_comp:
            deg = len(adj.get(rel, set()))
            if deg <= 2:
                low_degree.append((rel, deg))
low_degree.sort(key=lambda x: x[1])
for n, d in low_degree[:30]:
    print(f"  degree={d}: {n}")
if len(low_degree) > 30:
    print(f"  ... +{len(low_degree)-30} more low-degree nodes")
