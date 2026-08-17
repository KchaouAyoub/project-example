import os
import sys
import ast
import argparse
import subprocess
from typing import List, Dict, Any, Set, Optional
from datetime import datetime

# -- EXTRACTION DES FONCTIONS (AST) --

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def extract_functions(code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
    """
    Extrait toutes les fonctions d'un code source Python.
    Support : sync, async, méthodes de classe, décorateurs, types de retour.
    """
    functions = []

    try:
        tree = ast.parse(code)

        def visit(node, class_name: str = None):
            for child in ast.iter_child_nodes(node):
                # Entrer dans les classes
                if isinstance(child, ast.ClassDef):
                    visit(child, class_name=child.name)

                # Détecter les fonctions
                elif isinstance(child, FUNC_TYPES):
                    # Nom qualifié : "Classe.methode"
                    full_name = f"{class_name}.{child.name}" if class_name else child.name

                    # Type de retour
                    return_type = "Any"
                    if child.returns:
                        try:
                            return_type = ast.unparse(child.returns)
                        except:
                            return_type = "Any"

                    # Décorateurs
                    decorators = []
                    for d in child.decorator_list:
                        try:
                            decorators.append(ast.unparse(d))
                        except:
                            decorators.append("unknown")

                    info = {
                        'name': full_name,
                        'params': [a.arg for a in child.args.args],
                        'defaults': [ast.unparse(v) for v in child.args.defaults],
                        'return_type': return_type,
                        'is_async': isinstance(child, ast.AsyncFunctionDef),
                        'is_method': class_name is not None,
                        'decorators': decorators,
                        'docstring': ast.get_docstring(child) or "",
                        'file': os.path.basename(filename),
                    }
                    functions.append(info)

                    # Fonctions imbriquées
                    visit(child)

        visit(tree)

    except SyntaxError as e:
        print(f"Erreur syntaxe dans {filename}: {e}")

    return functions


# -- COMPARAISON --

def compare_apis(v1: List[Dict], v2: List[Dict]) -> Dict[str, List]:
    """Compare deux listes de fonctions."""
    changes = {'added': [], 'removed': [], 'modified': []}

    d1 = {f['name']: f for f in v1}
    d2 = {f['name']: f for f in v2}

    # Ajoutées
    for name, func in d2.items():
        if name not in d1:
            changes['added'].append({
                'name': name,
                'params': func.get('params', []),
                'file': func.get('file', ''),
                'is_async': func.get('is_async', False),
                'return_type': func.get('return_type', 'Any'),
            })

    # Supprimées
    for name, func in d1.items():
        if name not in d2:
            changes['removed'].append({
                'name': name,
                'params': func.get('params', []),
                'file': func.get('file', ''),
                'is_async': func.get('is_async', False),
                'return_type': func.get('return_type', 'Any'),
            })

    # Modifiées
    for name, f2 in d2.items():
        if name in d1:
            f1 = d1[name]

            params_changed = f1.get('params') != f2.get('params')
            return_changed = f1.get('return_type') != f2.get('return_type')
            async_changed = f1.get('is_async') != f2.get('is_async')
            decorators_changed = f1.get('decorators') != f2.get('decorators')

            if params_changed or return_changed or async_changed or decorators_changed:
                mod = {
                    'name': name,
                    'file': f2.get('file', ''),
                    'old_params': f1.get('params', []),
                    'new_params': f2.get('params', []),
                }
                if return_changed:
                    mod['old_return'] = f1.get('return_type', 'Any')
                    mod['new_return'] = f2.get('return_type', 'Any')
                if async_changed:
                    mod['old_async'] = f1.get('is_async', False)
                    mod['new_async'] = f2.get('is_async', False)
                if decorators_changed:
                    mod['old_decorators'] = f1.get('decorators', [])
                    mod['new_decorators'] = f2.get('decorators', [])
                changes['modified'].append(mod)

    return changes


# -- GIT --

def git_cmd(repo: str, *args) -> str:
    """Exécute une commande Git."""
    r = subprocess.run(['git', *args], cwd=repo, text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"Git failed: {' '.join(args)}")
    return r.stdout.strip()


def is_git_repo(repo: str) -> bool:
    """Vérifie si c'est un repo Git."""
    try:
        git_cmd(repo, 'rev-parse', '--is-inside-work-tree')
        return True
    except:
        return False


def list_py_at_ref(repo: str, ref: str) -> List[str]:
    """Liste les fichiers .py à une ref Git."""
    try:
        out = git_cmd(repo, 'ls-tree', '-r', '--name-only', ref)
        return sorted([f for f in out.splitlines() if f.endswith('.py')])
    except:
        return []


def read_from_git(repo: str, path: str, ref: str) -> str:
    """Lit un fichier depuis Git."""
    try:
        return git_cmd(repo, 'show', f'{ref}:{path}')
    except:
        return ''


def list_py_local(repo: str) -> List[str]:
    """Liste les fichiers .py sur le disque."""
    files = []
    for root, dirs, names in os.walk(repo):
        if '.git' in root or '__pycache__' in root:
            continue
        for n in names:
            if n.endswith('.py'):
                rel = os.path.relpath(os.path.join(root, n), repo).replace('\\', '/')
                files.append(rel)
    return sorted(files)


def read_local(repo: str, path: str) -> str:
    """Lit un fichier depuis le disque."""
    full = os.path.join(repo, path)
    if not os.path.exists(full):
        return ''
    with open(full, 'r', encoding='utf-8') as f:
        return f.read()


# -- TESTS IMPACTÉS --

def find_impacted_tests(test_path: str, changed_funcs: List[str]) -> List[str]:
    """Trouve les tests qui appellent des fonctions modifiées."""
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

    except Exception as e:
        print(f"Erreur test {test_path}: {e}")

    return sorted(impacted)


def find_test_dirs(repo: str) -> List[str]:
    """Trouve les dossiers de tests automatiquement."""
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


# -- DÉTECTION DES CHANGEMENTS --

def detect_changes(repo: str, old_ref: str, new_ref: str, verbose: bool = False) -> Dict:
    """Détecte les changements d'API dans tout le repository."""
    changes = {'added': [], 'removed': [], 'modified': []}

    if verbose:
        print(f"🔍 Analyse du repository : {repo}")
        print(f"🔀 Comparaison : {old_ref} → {new_ref}")

    if not is_git_repo(repo):
        raise ValueError(f"{repo} n'est pas un repo Git")

    # Récupérer les fichiers des deux versions
    if old_ref == new_ref:
        old_files = set(list_py_at_ref(repo, old_ref))
        new_files = set(list_py_local(repo))
        if verbose:
            print(f"📁 {len(old_files)} fichiers dans HEAD")
            print(f"📁 {len(new_files)} fichiers dans le working tree")
    else:
        old_files = set(list_py_at_ref(repo, old_ref))
        new_files = set(list_py_at_ref(repo, new_ref))
        if verbose:
            print(f"📁 {len(old_files)} fichiers dans {old_ref}")
            print(f"📁 {len(new_files)} fichiers dans {new_ref}")

    all_files = sorted(old_files | new_files)

    for path in all_files:
        if verbose:
            print(f"   📄 Analyse de {path}...")

        # Lire les sources
        old_src = read_from_git(repo, path, old_ref) if path in old_files else ''
        new_src = read_local(repo, path) if path in new_files and old_ref == new_ref else ''
        if old_ref != new_ref and path in new_files:
            new_src = read_from_git(repo, path, new_ref)

        # Extraire et comparer
        old_funcs = extract_functions(old_src, path)
        new_funcs = extract_functions(new_src, path)
        file_changes = compare_apis(old_funcs, new_funcs)

        changes['added'].extend(file_changes['added'])
        changes['removed'].extend(file_changes['removed'])
        changes['modified'].extend(file_changes['modified'])

    if verbose:
        print(f"\n📊 Résumé : {len(changes['added'])} ajoutées, {len(changes['removed'])} supprimées, {len(changes['modified'])} modifiées")

    return changes


# -- RAPPORT --

def format_params(p: List[str]) -> str:
    return ', '.join(p) if p else ''


def print_report(changes: Dict, impacted: List[str] = None):
    """Affiche le rapport avec emojis."""
    print("\n" + "=" * 70)
    print("RAPPORT DES CHANGEMENTS D'API")
    print("=" * 70)

    print(f"\nRésumé:")
    print(f"   Ajoutées   : {len(changes['added'])}")
    print(f"   Supprimées : {len(changes['removed'])}")
    print(f"   Modifiées  : {len(changes['modified'])}")

    if changes['added']:
        print("\nFONCTIONS AJOUTÉES:")
        for f in changes['added']:
            p = format_params(f.get('params', []))
            pref = "async " if f.get('is_async') else ""
            print(f" [{f.get('file', '')}] {pref}{f['name']}({p})")

    if changes['removed']:
        print("\nFONCTIONS SUPPRIMÉES:")
        for f in changes['removed']:
            p = format_params(f.get('params', []))
            pref = "async " if f.get('is_async') else ""
            print(f" [{f.get('file', '')}] {pref}{f['name']}({p})")

    if changes['modified']:
        print("\nFONCTIONS MODIFIÉES:")
        for f in changes['modified']:
            old = format_params(f['old_params'])
            new = format_params(f['new_params'])
            print(f" [{f.get('file', '')}] {f['name']}: ({old}) -> ({new})")
            if 'old_return' in f:
                print(f"       Retour: {f['old_return']} -> {f['new_return']}")
            if 'old_async' in f:
                print(f"       Async: {f['old_async']} -> {f['new_async']}")

    print("\n" + "=" * 70)

    if impacted:
        print(f"\nTESTS IMPACTÉS ({len(impacted)})")
        print("=" * 70)
        for t in impacted:
            print(f"   - {t}()")
        print("=" * 70)


# -- MAIN --

def main():
    parser = argparse.ArgumentParser(
        description="📊 API Change Tracker - Détecte les changements d'API",
        epilog="Ex: python api_tracker.py . --old-ref HEAD~1 --new-ref HEAD"
    )
    parser.add_argument('path', nargs='?', default=os.getcwd(),
                        help="Chemin du repo (défaut: courant)")
    parser.add_argument('--old-ref', default='HEAD',
                        help="Référence Git ancienne")
    parser.add_argument('--new-ref', default='HEAD',
                        help="Référence Git nouvelle")
    parser.add_argument('--include', default='*.py',
                        help="Pattern d'inclusion")
    parser.add_argument('--exclude', default='',
                        help="Pattern d'exclusion")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Mode détaillé")
    parser.add_argument('--output', '-o',
                        help="Génère un rapport HTML (ex: report.html)")
    parser.add_argument('--json', '-j',
                        help="Exporte les résultats en JSON (ex: report.json)")

    args = parser.parse_args()

    if args.verbose:
        print(f"🔍 Mode verbose activé")
        print(f"📂 Repository: {args.path}")
        print(f"🔀 Comparaison: {args.old_ref} → {args.new_ref}")

    try:
        changes = detect_changes(args.path, args.old_ref, args.new_ref, args.verbose)

        # Trouver les tests impactés
        changed_funcs = (
            [f['name'] for f in changes['modified']] +
            [f['name'] for f in changes['added']] +
            [f['name'] for f in changes['removed']]
        )
        impacted_tests = []
        if changed_funcs:
            for d in find_test_dirs(args.path):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith('.py'):
                            impacted_tests.extend(find_impacted_tests(
                                os.path.join(root, f), changed_funcs
                            ))
            impacted_tests = sorted(set(impacted_tests))

        # Afficher le rapport console
        print_report(changes, impacted_tests)

        # 👇 NOUVEAU : Générer les rapports si demandés 👇
        if args.output:
            generate_html_report(changes, impacted_tests, args.output)

        if args.json:
            export_json(changes, impacted_tests, args.json)

    except ValueError as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
def generate_html_report(changes: Dict, impacted_tests: List[str], output_path: str = "report.html"):
    """Génère un rapport HTML professionnel."""
    
    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Change Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            padding: 40px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a1a2e;
            border-bottom: 4px solid #007bff;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        .meta {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 30px;
            font-size: 14px;
            color: #495057;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .card {{
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            font-size: 1.2rem;
        }}
        .card-added {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
        .card-removed {{ background: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }}
        .card-modified {{ background: #fff3cd; color: #856404; border-left: 5px solid #ffc107; }}
        .card-total {{ background: #cce5ff; color: #004085; border-left: 5px solid #17a2b8; }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #1a1a2e;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .function-item {{
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 6px;
            margin: 5px 0;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            border-left: 4px solid #007bff;
        }}
        .function-item.added {{ border-left-color: #28a745; }}
        .function-item.removed {{ border-left-color: #dc3545; }}
        .function-item.modified {{ border-left-color: #ffc107; }}
        .test-item {{
            background: #f8f9fa;
            padding: 8px 15px;
            border-radius: 6px;
            margin: 4px 0;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #6c757d;
            font-size: 14px;
            border-top: 1px solid #e9ecef;
            padding-top: 20px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            color: white;
            margin-left: 10px;
        }}
        .badge-added {{ background: #28a745; }}
        .badge-removed {{ background: #dc3545; }}
        .badge-modified {{ background: #ffc107; color: #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 API Change Report</h1>
        
        <div class="meta">
            <strong>Repository:</strong> {os.getcwd()}<br>
            <strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="summary">
            <div class="card card-added">✅ Added: {len(changes.get('added', []))}</div>
            <div class="card card-removed">❌ Removed: {len(changes.get('removed', []))}</div>
            <div class="card card-modified">⚠️ Modified: {len(changes.get('modified', []))}</div>
            <div class="card card-total">📈 Total: {len(changes.get('added', [])) + len(changes.get('removed', [])) + len(changes.get('modified', []))}</div>
        </div>
"""

    if changes.get('added'):
        html += """
        <div class="section">
            <h2>🟢 Functions Added</h2>
"""
        for f in changes['added']:
            html += f"""
            <div class="function-item added">✅ {f.get('file', '')} :: {f['name']}({', '.join(f.get('params', []))})</div>
"""
        html += "</div>"

    if changes.get('removed'):
        html += """
        <div class="section">
            <h2>🔴 Functions Removed</h2>
"""
        for f in changes['removed']:
            html += f"""
            <div class="function-item removed">❌ {f.get('file', '')} :: {f['name']}({', '.join(f.get('params', []))})</div>
"""
        html += "</div>"

    if changes.get('modified'):
        html += """
        <div class="section">
            <h2>🟡 Functions Modified</h2>
"""
        for f in changes['modified']:
            old = ', '.join(f.get('old_params', []))
            new = ', '.join(f.get('new_params', []))
            html += f"""
            <div class="function-item modified">⚠️ {f.get('file', '')} :: {f['name']}: ({old}) → ({new})</div>
"""
        html += "</div>"

    if impacted_tests:
        html += """
        <div class="section">
            <h2>🧪 Impacted Tests ({len(impacted_tests)})</h2>
"""
        for test in impacted_tests:
            html += f"""
            <div class="test-item">🧪 {test}()</div>
"""
        html += "</div>"

    html += """
        <div class="footer">
            Generated by <strong>API Change Tracker</strong> v1.0
        </div>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Rapport HTML généré : {output_path}")
def export_json(changes: Dict, impacted_tests: List[str], output_path: str = "report.json"):
    """Exporte les résultats en JSON."""
    import json
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "added": len(changes.get('added', [])),
            "removed": len(changes.get('removed', [])),
            "modified": len(changes.get('modified', [])),
            "total": len(changes.get('added', [])) + len(changes.get('removed', [])) + len(changes.get('modified', []))
        },
        "changes": changes,
        "impacted_tests": impacted_tests
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Rapport JSON généré : {output_path}")

if __name__ == "__main__":
    main()