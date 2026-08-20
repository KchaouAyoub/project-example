"""
extractors/java_extractor.py - Extracteur pour Java
"""

import hashlib
from typing import List, Dict, Any
from .base import BaseExtractor

try:
    import javalang
except ImportError:
    javalang = None

class JavaExtractor(BaseExtractor):
    """Extracteur pour le langage Java."""
    
    def extract(self, code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
        if javalang is None:
            return self._extract_without_javalang(code, filename)

        functions = []
        try:
            tree = javalang.parse.parse(code)
            
            # Parcourir l'arbre syntaxique
            for path, node in tree:
                # Détecter les méthodes
                if isinstance(node, javalang.tree.MethodDeclaration):
                    name = node.name
                    params = []
                    param_types = []
                    if node.parameters:
                        for p in node.parameters:
                            param_name = p.name
                            # Type du paramètre
                            if p.type:
                                param_type = str(p.type)
                            else:
                                param_type = "Object"
                            params.append(param_name)
                            param_types.append(param_type)
                    
                    # Type de retour
                    return_type = "void"
                    if node.return_type:
                        return_type = str(node.return_type)
                    
                    # Modificateurs (public, static, etc.)
                    decorators = []
                    if node.modifiers:
                        decorators = node.modifiers
                    
                    # Vérifier les annotations
                    if node.annotations:
                        for anno in node.annotations:
                            decorators.append(f"@{anno.name}")
                    
                    body_hash = hashlib.sha256(
                        str(node).encode('utf-8')
                    ).hexdigest()
                    
                    functions.append({
                        'name': name,
                        'params': params,
                        'param_types': param_types,
                        'return_type': return_type,
                        'is_async': False,  # Java n'a pas d'async
                        'decorators': decorators,
                        'body_hash': body_hash,
                        'file': filename,
                        'signature': f"{return_type} {name}({', '.join(params)})"
                    })
                
                # Détecter les constructeurs
                elif isinstance(node, javalang.tree.ConstructorDeclaration):
                    name = node.name
                    params = []
                    param_types = []
                    if node.parameters:
                        for p in node.parameters:
                            params.append(p.name)
                            param_types.append(str(p.type) if p.type else "Object")
                    
                    decorators = []
                    if node.modifiers:
                        decorators = node.modifiers
                    
                    functions.append({
                        'name': f"{name} (constructeur)",
                        'params': params,
                        'param_types': param_types,
                        'return_type': "constructor",
                        'is_async': False,
                        'decorators': decorators,
                        'body_hash': hashlib.sha256(str(node).encode('utf-8')).hexdigest(),
                        'file': filename,
                        'signature': f"{name}({', '.join(params)})"
                    })
                    
        except Exception as e:
            print(f"⚠️ Erreur parsing Java: {e}")
        
        return functions

    def _extract_without_javalang(self, code: str, filename: str) -> List[Dict[str, Any]]:
        """Fallback pour garder Java exploitable sans dependance optionnelle."""
        from .cpp_extractor import CppExtractor

        functions = CppExtractor().extract(code, filename)
        for function in functions:
            function["return_type"] = function["return_type"].replace("public ", "").replace("private ", "").replace("protected ", "").strip()
            function["signature"] = f"{function['return_type']} {function['name']}({', '.join(function['params'])})"
        return functions
    
    def supported_extensions(self) -> List[str]:
        return ['.java']
    
    def language_name(self) -> str:
        return "Java"