"""
extractors/python_extractor.py - Extracteur pour Python
"""

import ast
import hashlib
from typing import List, Dict, Any
from .base import BaseExtractor


class PythonExtractor(BaseExtractor):
    """Extracteur Python base sur l'AST standard."""

    def extract(self, code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
        functions: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(code, filename=filename)
        except (SyntaxError, ValueError, TypeError):
            return functions

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            params = [argument.arg for argument in node.args.args]
            if node.args.posonlyargs:
                params = [argument.arg for argument in node.args.posonlyargs] + params
            if node.args.vararg:
                params.append(f"*{node.args.vararg.arg}")
            params.extend(argument.arg for argument in node.args.kwonlyargs)
            if node.args.kwarg:
                params.append(f"**{node.args.kwarg.arg}")

            return_type = "Any"
            if node.returns is not None:
                try:
                    return_type = ast.unparse(node.returns)
                except (AttributeError, ValueError):
                    pass

            decorators = []
            for decorator in node.decorator_list:
                try:
                    decorators.append(ast.unparse(decorator))
                except (AttributeError, ValueError):
                    decorators.append("...")

            body_hash = hashlib.sha256(
                ast.dump(node, include_attributes=False).encode("utf-8")
            ).hexdigest()
            async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            functions.append({
                "name": node.name,
                "params": params,
                "param_types": [
                    ast.unparse(argument.annotation) if argument.annotation is not None else "Any"
                    for argument in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                ],
                "return_type": return_type,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorators": decorators,
                "body_hash": body_hash,
                "file": filename,
                "signature": f"{async_prefix}{node.name}({', '.join(params)}) -> {return_type}",
            })

        return functions

    def supported_extensions(self) -> List[str]:
        return [".py", ".pyw"]

    def language_name(self) -> str:
        return "Python"
