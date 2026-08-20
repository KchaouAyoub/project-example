import os
import sys
import ast
import json
import argparse
import subprocess
from typing import List, Dict, Any, Set
from datetime import datetime
from extractors import SUPPORTED_EXTENSIONS, extract_functions as extract_source_functions

# Gestion des erreurs (sans UnicodeError)

def error(msg: str):
    try:
        print(f"\033[91m[ERREUR] {msg}\033[0m")
    except:
        print(f"[ERREUR] {msg}")

def warning(msg: str):
    try:
        print(f"\033[93m[AVERTISSEMENT] {msg}\033[0m")
    except:
        print(f"[AVERTISSEMENT] {msg}")

def info(msg: str):
    try:
        print(f"\033[94m[INFO] {msg}\033[0m")
    except:
        print(f"[INFO] {msg}")

def success(msg: str):
    try:
        print(f"\033[92m[SUCCES] {msg}\033[0m")
    except:
        print(f"[SUCCES] {msg}")

# Extraction des fonctions

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)

def extract_functions(code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
    return extract_source_functions(code, filename)

def compare_apis(v1: List[Dict], v2: List[Dict]) -> Dict:
    changes = {'added': [], 'removed': [], 'modified': []}
    d1 = {f['name']: f for f in v1}
    d2 = {f['name']: f for f in v2}
    for name, func in d2.items():
        if name not in d1:
            changes['added'].append(func)
    for name, func in d1.items():
        if name not in d2:
            changes['removed'].append(func)
    for name, func2 in d2.items():
        if name in d1:
            func1 = d1[name]
            old_params = func1.get('params', [])
            new_params = func2.get('params', [])
            old_param_types = func1.get('param_types', [])
            new_param_types = func2.get('param_types', [])
            old_return = func1.get('return_type', 'Any')
            new_return = func2.get('return_type', 'Any')
            old_async = func1.get('is_async', False)
            new_async = func2.get('is_async', False)
            body_changed = (
                func1.get('body_hash') is not None and
                func2.get('body_hash') is not None and
                func1.get('body_hash') != func2.get('body_hash')
            )
            if (
                old_params != new_params or
                old_param_types != new_param_types or
                old_return != new_return or
                old_async != new_async or
                body_changed
            ):
                changes['modified'].append({
                    'name': name,
                    'file': func2.get('file', ''),
                    'old_params': old_params,
                    'new_params': new_params,
                    'old_param_types': old_param_types,
                    'new_param_types': new_param_types,
                    'old_return': old_return,
                    'new_return': new_return,
                    'old_async': old_async,
                    'new_async': new_async,
                    'params_added': [p for p in new_params if p not in old_params],
                    'params_removed': [p for p in old_params if p not in new_params],
                    'param_types_changed': old_param_types != new_param_types,
                    'old_signature': func1.get('signature', name),
                    'new_signature': func2.get('signature', name),
                    'body_changed': body_changed,
                })
    return changes

# Git

def git_cmd(repo: str, *args) -> str:
    try:
        r = subprocess.run(
            ['git', *args],
            cwd=repo,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"Git failed: {' '.join(args)}")
        return r.stdout.strip()
    except Exception as e:
        raise RuntimeError(str(e))

def is_git_repo(repo: str) -> bool:
    try:
        git_cmd(repo, 'rev-parse', '--is-inside-work-tree')
        return True
    except:
        return False

def list_py_at_ref(repo: str, ref: str) -> List[str]:
    try:
        out = git_cmd(repo, 'ls-tree', '-r', '--name-only', ref)
        return sorted([
            f for f in out.splitlines()
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ])
    except:
        return []

def read_from_git(repo: str, path: str, ref: str) -> str:
    try:
        return git_cmd(repo, 'show', f'{ref}:{path}')
    except:
        return ''

def list_py_local(repo: str) -> List[str]:
    files = []
    for root, dirs, names in os.walk(repo):
        if '.git' in root or '__pycache__' in root:
            continue
        for n in names:
            if os.path.splitext(n)[1].lower() in SUPPORTED_EXTENSIONS:
                rel = os.path.relpath(os.path.join(root, n), repo).replace('\\', '/')
                files.append(rel)
    return sorted(files)

def read_local(repo: str, path: str) -> str:
    full = os.path.join(repo, path)
    if not os.path.exists(full):
        return ''
    with open(full, 'r', encoding='utf-8') as f:
        return f.read()

# Tests impactés

def find_impacted_tests(test_path: str, changed_funcs: List[str]) -> List[str]:
    impacted = set()
    try:
        with open(test_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        short_names = {n.split('.')[-1] for n in changed_funcs}
        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.current = None
            def visit_FunctionDef(self, node):
                prev = self.current
                self.current = node.name
                self.generic_visit(node)
                self.current = prev
            def visit_AsyncFunctionDef(self, node):
                prev = self.current
                self.current = node.name
                self.generic_visit(node)
                self.current = prev
            def visit_Call(self, node):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in short_names and self.current:
                    impacted.add(self.current)
                self.generic_visit(node)
        Visitor().visit(tree)
    except Exception:
        pass
    return sorted(impacted)

def find_test_dirs(repo: str) -> List[str]:
    dirs = set()
    patterns = ['tests', 'test', 'testing', 'unittest']
    for root, _, files in os.walk(repo):
        if '.git' in root:
            continue
        base = os.path.basename(root).lower()
        if any(p in base for p in patterns):
            dirs.add(root)
        for f in files:
            if f.startswith('test_') and f.endswith('.py'):
                dirs.add(root)
                break
    return sorted(dirs)

# Détection des changements

def detect_changes(repo: str, old_ref: str, new_ref: str, verbose: bool = False) -> Dict:
    changes = {'added': [], 'removed': [], 'modified': []}
    if not is_git_repo(repo):
        raise ValueError(f"{repo} n'est pas un repo Git")
    if old_ref == new_ref:
        old_files = set(list_py_at_ref(repo, old_ref))
        new_files = set(list_py_local(repo))
    else:
        old_files = set(list_py_at_ref(repo, old_ref))
        new_files = set(list_py_at_ref(repo, new_ref))
    all_files = sorted(old_files | new_files)
    for path in all_files:
        old_src = read_from_git(repo, path, old_ref) if path in old_files else ''
        new_src = read_local(repo, path) if path in new_files and old_ref == new_ref else ''
        if old_ref != new_ref and path in new_files:
            new_src = read_from_git(repo, path, new_ref)
        old_funcs = extract_functions(old_src, path)
        new_funcs = extract_functions(new_src, path)
        file_changes = compare_apis(old_funcs, new_funcs)
        changes['added'].extend(file_changes['added'])
        changes['removed'].extend(file_changes['removed'])
        changes['modified'].extend(file_changes['modified'])
    return changes

# Rapport HTML

def generate_html_report(changes: Dict, impacted_tests: List[str], output_path: str = "report.html"):
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>API Change Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--ink:#172033;--muted:#64748b;--line:#d8e0ea;--panel:#f7f9fc;--primary:#1769e0}}
body{{font-family:'Trebuchet MS','Segoe UI',sans-serif;color:var(--ink);background:linear-gradient(135deg,#edf3fb 0%,#f8fafc 52%,#eef2f7 100%);padding:32px 20px;min-height:100vh}}
.container{{max-width:1120px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:18px;padding:34px;box-shadow:0 18px 45px rgba(23,32,51,.1)}}
h1{{color:var(--primary);border-bottom:3px solid var(--primary);padding-bottom:18px;margin-bottom:30px;font-size:clamp(1.8rem,4vw,2.7rem);letter-spacing:-.03em}}
.meta{{background:var(--panel);padding:15px;border:1px solid var(--line);border-radius:8px;margin-bottom:30px;font-size:14px;color:var(--muted)}}
.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:40px}}
.card{{padding:20px;border:1px solid var(--line);border-radius:10px;text-align:center;font-weight:bold;font-size:1.2rem}}
.card-added{{background:#e8f6ee;color:#146c43;border-left:5px solid #198754}}
.card-removed{{background:#fbecef;color:#a23146;border-left:5px solid #c24156}}
.card-modified{{background:#fff7df;color:#946c00;border-left:5px solid #d39e00}}
.card-total{{background:#e8f2ff;color:#1456a0;border-left:5px solid #1769e0}}
.section{{margin-bottom:30px}}
.section h2{{color:var(--ink);border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:15px}}
.function-item{{padding:12px 15px;border:1px solid var(--line);border-radius:8px;margin:6px 0;font-family:monospace;font-size:14px}}
.function-added{{background:#e8f6ee;border-left:4px solid #198754}}
.function-removed{{background:#fbecef;border-left:4px solid #c24156}}
.function-modified{{background:#fff7df;border-left:4px solid #d39e00}}
.test-item{{background:var(--panel);padding:10px 15px;border:1px solid var(--line);border-radius:8px;margin:5px 0;font-family:monospace;font-size:14px}}
.footer{{margin-top:40px;text-align:center;color:var(--muted);font-size:14px;border-top:1px solid var(--line);padding-top:20px}}
@media (max-width:768px){{.summary{{grid-template-columns:repeat(2,1fr)}}body{{padding:16px 10px}}.container{{padding:22px}}}}
</style>
</head>
<body>
<div class="container">
<h1>API Change Report</h1>
<div class="meta"><strong>Repository:</strong> {os.getcwd()}<br><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="summary">
<div class="card card-added">Added: {len(changes.get('added', []))}</div>
<div class="card card-removed">Removed: {len(changes.get('removed', []))}</div>
<div class="card card-modified">Modified: {len(changes.get('modified', []))}</div>
<div class="card card-total">Total: {len(changes.get('added', [])) + len(changes.get('removed', [])) + len(changes.get('modified', []))}</div>
</div>
"""
    if changes.get('added'):
        html += '<div class="section"><h2>Functions Added</h2>'
        for f in changes['added']:
            html += f'<div class="function-item function-added">{f.get("file","")} :: {f["name"]}({", ".join(f.get("params", []))})</div>'
        html += '</div>'
    if changes.get('removed'):
        html += '<div class="section"><h2>Functions Removed</h2>'
        for f in changes['removed']:
            html += f'<div class="function-item function-removed">{f.get("file","")} :: {f["name"]}({", ".join(f.get("params", []))})</div>'
        html += '</div>'
    if changes.get('modified'):
        html += '<div class="section"><h2>Functions Modified</h2>'
        for f in changes['modified']:
            old = ', '.join(f.get('old_params', []))
            new = ', '.join(f.get('new_params', []))
            html += f'<div class="function-item function-modified">{f.get("file","")} :: {f["name"]}: ({old}) → ({new})</div>'
        html += '</div>'
    if impacted_tests:
        html += f'<div class="section"><h2>Impacted Tests ({len(impacted_tests)})</h2>'
        for t in impacted_tests:
            html += f'<div class="test-item">{t}()</div>'
        html += '</div>'
    html += '<div class="footer">Generated by <strong>API Change Tracker</strong> v1.0</div></div></body></html>'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path

# Main

def main():
    parser = argparse.ArgumentParser(description="API Change Tracker")
    parser.add_argument('path', nargs='?', default=os.getcwd(), help="Chemin du repo")
    parser.add_argument('--old-ref', default='HEAD', help="Ancienne référence")
    parser.add_argument('--new-ref', default='HEAD', help="Nouvelle référence")
    parser.add_argument('--output', '-o', help="Rapport HTML")
    parser.add_argument('--verbose', '-v', action='store_true', help="Mode détaillé")
    args = parser.parse_args()
    try:
        changes = detect_changes(args.path, args.old_ref, args.new_ref, args.verbose)
        changed_funcs = [f['name'] for f in changes['modified']] + [f['name'] for f in changes['added']] + [f['name'] for f in changes['removed']]
        impacted = []
        if changed_funcs:
            for d in find_test_dirs(args.path):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith('.py'):
                            impacted.extend(find_impacted_tests(os.path.join(root, f), changed_funcs))
            impacted = sorted(set(impacted))
        if args.output:
            generate_html_report(changes, impacted, args.output)
            print(f"Rapport généré: {args.output}")
        else:
            print(f"\nRésumé:")
            print(f"  Ajoutées: {len(changes['added'])}")
            print(f"  Supprimées: {len(changes['removed'])}")
            print(f"  Modifiées: {len(changes['modified'])}")
            if impacted:
                print(f"  Tests impactés: {len(impacted)}")
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()