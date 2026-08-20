import os
import sys
import json
import ast
import subprocess
import tempfile
import hashlib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from extractors import SUPPORTED_EXTENSIONS, extract_functions as extract_source_functions

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api_tracker import detect_changes, is_git_repo, find_test_dirs, find_impacted_tests
except ImportError:
    print("api_tracker.py non trouvé")
    sys.exit(1)

app = FastAPI(title="API Change Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    repo_path: str
    old_ref: str = "HEAD"
    new_ref: str = "HEAD"

class SnapshotRequest(BaseModel):
    repo_path: str

# Fonctions d'extraction

def extract_all_functions(code: str, filename: str = "<memory>") -> List[Dict]:
    """
    Extrait TOUTES les fonctions avec leurs détails complets.
    """
    return extract_source_functions(code, filename)


def compare_functions_deep(old_funcs: List[Dict], new_funcs: List[Dict]) -> Dict:
    """
    Compare deux listes de fonctions de manière DÉTAILLÉE.
    """
    changes = {'added': [], 'removed': [], 'modified': []}
    
    old_dict = {f['name']: f for f in old_funcs}
    new_dict = {f['name']: f for f in new_funcs}
    
    # Fonctions AJOUTÉES
    for name, func in new_dict.items():
        if name not in old_dict:
            changes['added'].append({
                'name': name,
                'params': func.get('params', []),
                'return_type': func.get('return_type', 'Any'),
                'is_async': func.get('is_async', False),
                'signature': func.get('signature', name),
                'file': func.get('file', '')
            })
    
    # Fonctions SUPPRIMÉES
    for name, func in old_dict.items():
        if name not in new_dict:
            changes['removed'].append({
                'name': name,
                'params': func.get('params', []),
                'return_type': func.get('return_type', 'Any'),
                'is_async': func.get('is_async', False),
                'signature': func.get('signature', name),
                'file': func.get('file', '')
            })
    
    # Fonctions MODIFIÉES
    for name, new_func in new_dict.items():
        if name in old_dict:
            old_func = old_dict[name]
            
            old_params = old_func.get('params', [])
            new_params = new_func.get('params', [])
            old_param_types = old_func.get('param_types', [])
            new_param_types = new_func.get('param_types', [])
            old_return = old_func.get('return_type', 'Any')
            new_return = new_func.get('return_type', 'Any')
            old_async = old_func.get('is_async', False)
            new_async = new_func.get('is_async', False)
            body_changed = (
                old_func.get('body_hash') is not None and
                new_func.get('body_hash') is not None and
                old_func.get('body_hash') != new_func.get('body_hash')
            )
            
            params_changed = old_params != new_params
            param_types_changed = old_param_types != new_param_types
            return_changed = old_return != new_return
            async_changed = old_async != new_async
            
            if params_changed or param_types_changed or return_changed or async_changed or body_changed:
                changes['modified'].append({
                    'name': name,
                    'file': new_func.get('file', ''),
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
                    'param_types_changed': param_types_changed,
                    'old_signature': old_func.get('signature', name),
                    'new_signature': new_func.get('signature', name),
                    'body_changed': body_changed
                })
    
    return changes


def scan_source_files(repo_path: str) -> Dict[str, str]:
    """Scanne les fichiers source pris en charge par les extracteurs."""
    snapshot = {}
    for root, dirs, files in os.walk(repo_path):
        if '.git' in root or '__pycache__' in root or '.api_snapshot' in root or 'node_modules' in root:
            continue
        for file in files:
            if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path).replace('\\', '/')
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        snapshot[rel_path] = f.read()
                except:
                    pass
    return snapshot


scan_all_python_files = scan_source_files

# Endpoints

@app.get("/")
def root():
    return {"message": "API Change Tracker", "status": "running"}

@app.get("/branches")
def list_branches(repo_path: str):
    try:
        r = subprocess.run(['git', 'branch', '--format=%(refname:short)'], cwd=repo_path, text=True, capture_output=True)
        return {"branches": [b.strip() for b in r.stdout.splitlines() if b.strip()]}
    except:
        return {"branches": []}

@app.get("/commits")
def list_commits(repo_path: str, limit: int = 10):
    try:
        r = subprocess.run(['git', 'log', f'-{limit}', '--format=%h||%s||%an||%ar'], cwd=repo_path, text=True, capture_output=True)
        commits = []
        for line in r.stdout.splitlines():
            if '||' in line:
                parts = line.split('||')
                commits.append({
                    'hash': parts[0],
                    'message': parts[1] if len(parts) > 1 else '',
                    'author': parts[2] if len(parts) > 2 else '',
                    'date': parts[3] if len(parts) > 3 else ''
                })
        return {"commits": commits}
    except:
        return {"commits": []}

@app.get("/check-git")
def check_git(repo_path: str):
    try:
        return {"is_git": is_git_repo(repo_path)}
    except:
        return {"is_git": False}

# Analyse Git

@app.post("/analyze")
def analyze(request: AnalysisRequest):
    try:
        changes = detect_changes(request.repo_path, request.old_ref, request.new_ref)
        changed_funcs = [f['name'] for f in changes['modified']] + [f['name'] for f in changes['added']] + [f['name'] for f in changes['removed']]
        impacted = []
        if changed_funcs:
            for d in find_test_dirs(request.repo_path):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith('.py'):
                            impacted.extend(find_impacted_tests(os.path.join(root, f), changed_funcs))
            impacted = sorted(set(impacted))
        return {
            "total": len(changes['added']) + len(changes['removed']) + len(changes['modified']),
            "added": len(changes['added']),
            "removed": len(changes['removed']),
            "modified": len(changes['modified']),
            "details": {"changes": changes, "impacted_tests": impacted}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Analyse sans Git (snapshot)

@app.post("/save-snapshot")
def save_snapshot(request: SnapshotRequest):
    try:
        if not os.path.exists(request.repo_path):
            return {"success": False, "error": "Repository not found"}
        
        snapshot = scan_all_python_files(request.repo_path)
        snapshot_path = os.path.join(request.repo_path, '.api_snapshot.json')
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
        
        return {
            "success": True,
            "message": f"Snapshot sauvegardé : {len(snapshot)} fichiers",
            "files_count": len(snapshot)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/analyze-no-git")
def analyze_no_git(request: SnapshotRequest):
    try:
        if not os.path.exists(request.repo_path):
            return {"error": "Repository not found", "need_snapshot": True}
        
        snapshot_path = os.path.join(request.repo_path, '.api_snapshot.json')
        
        try:
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                old_snapshot = json.load(f)
        except FileNotFoundError:
            return {
                "error": "Aucun snapshot trouvé. Veuillez d'abord sauvegarder l'état.",
                "need_snapshot": True
            }
        
        new_snapshot = scan_all_python_files(request.repo_path)
        
        all_files = set(old_snapshot.keys()) | set(new_snapshot.keys())
        
        all_added = []
        all_removed = []
        all_modified = []
        
        for file in all_files:
            old_code = old_snapshot.get(file, '')
            new_code = new_snapshot.get(file, '')
            
            old_funcs = extract_all_functions(old_code, file)
            new_funcs = extract_all_functions(new_code, file)
            
            changes = compare_functions_deep(old_funcs, new_funcs)
            
            for f in changes['added']:
                f['file'] = file
                all_added.append(f)
            
            for f in changes['removed']:
                f['file'] = file
                all_removed.append(f)
            
            for f in changes['modified']:
                f['file'] = file
                all_modified.append(f)
        
        total = len(all_added) + len(all_removed) + len(all_modified)
        
        return {
            "repo_path": request.repo_path,
            "total": total,
            "added": len(all_added),
            "removed": len(all_removed),
            "modified": len(all_modified),
            "details": {
                "changes": {
                    "added": all_added,
                    "removed": all_removed,
                    "modified": all_modified
                },
                "impacted_tests": []
            },
            "is_git": False,
            "analysis_type": "snapshot"
        }
    except Exception as e:
        return {"error": str(e), "need_snapshot": True}

# Rapport HTML

@app.post("/generate-report")
def generate_report(request: AnalysisRequest):
    try:
        from api_tracker import generate_html_report
        
        is_git = is_git_repo(request.repo_path)
        
        if is_git:
            changes = detect_changes(request.repo_path, request.old_ref, request.new_ref)
            changed_funcs = [f['name'] for f in changes['modified']] + [f['name'] for f in changes['added']] + [f['name'] for f in changes['removed']]
            impacted = []
            if changed_funcs:
                for d in find_test_dirs(request.repo_path):
                    for root, _, files in os.walk(d):
                        for f in files:
                            if f.endswith('.py'):
                                impacted.extend(find_impacted_tests(os.path.join(root, f), changed_funcs))
                impacted = sorted(set(impacted))
        else:
            snapshot_path = os.path.join(request.repo_path, '.api_snapshot.json')
            try:
                with open(snapshot_path, 'r', encoding='utf-8') as f:
                    old_snapshot = json.load(f)
            except:
                return {"success": False, "error": "Aucun snapshot trouvé pour ce dossier non-Git. Veuillez d'abord sauvegarder l'état."}
            
            new_snapshot = scan_all_python_files(request.repo_path)
            all_files = set(old_snapshot.keys()) | set(new_snapshot.keys())
            added, removed, modified = [], [], []
            
            for file in all_files:
                old_code = old_snapshot.get(file, '')
                new_code = new_snapshot.get(file, '')
                old_funcs = extract_all_functions(old_code, file)
                new_funcs = extract_all_functions(new_code, file)
                changes = compare_functions_deep(old_funcs, new_funcs)
                for f in changes['added']:
                    f['file'] = file
                    added.append(f)
                for f in changes['removed']:
                    f['file'] = file
                    removed.append(f)
                for f in changes['modified']:
                    f['file'] = file
                    modified.append(f)
            
            changes = {'added': added, 'removed': removed, 'modified': modified}
            impacted = []
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
            output_path = f.name
        
        generate_html_report(changes, impacted, output_path)
        
        with open(output_path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        os.unlink(output_path)
        return {"success": True, "html": html}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/interface")
def interface():
    html_path = os.path.join(os.path.dirname(__file__), "interface.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return {"error": "interface.html not found"}
@app.get("/check-path")
def check_path(path: str):
    """Vérifie si un dossier existe."""
    try:
        return {"exists": os.path.exists(path)}
    except Exception as e:
        return {"exists": False, "error": str(e)}

@app.get("/select-folder")
def select_folder():
    """Ouvre le sélecteur de dossiers sur la machine qui héberge l'API."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(title='Sélectionner un dossier Python')
        root.destroy()
        return {"selected": bool(selected), "path": selected}
    except Exception as e:
        return {"selected": False, "path": "", "error": str(e)}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)