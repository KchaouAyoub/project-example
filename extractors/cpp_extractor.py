"""
extractors/cpp_extractor.py - Extracteur leger pour C et C++
"""

import hashlib
import re
from typing import List, Dict, Any
from .base import BaseExtractor


_CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch"}
_FUNCTION_RE = re.compile(
    r"(?P<prefix>(?:(?:template\s*<[^;{}]+>\s*)|(?:[\w:\<\>~*&]+\s+))+)?"
    r"(?P<name>(?:[\w:]+::)*~?[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^()]*)\)\s*(?:const\s*)?(?:noexcept\s*)?\{",
    re.MULTILINE,
)


def _strip_comments(code: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.DOTALL)


def _matching_body_end(code: str, opening_brace: int) -> int:
    depth = 0
    for index in range(opening_brace, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(code)


def _parameter_names(parameters: str) -> List[str]:
    if not parameters.strip() or parameters.strip() == "void":
        return []
    names = []
    for parameter in parameters.split(","):
        parameter = parameter.split("=")[0].strip()
        match = re.search(r"([A-Za-z_]\w*)\s*(?:\[.*\])?$", parameter)
        names.append(match.group(1) if match else parameter)
    return names


def _parameter_types(parameters: str) -> List[str]:
    if not parameters.strip() or parameters.strip() == "void":
        return []
    types = []
    for parameter in parameters.split(","):
        parameter = parameter.split("=")[0].strip()
        match = re.match(r"(.+?)(?:[A-Za-z_]\w*)\s*(?:\[.*\])?$", parameter)
        types.append(match.group(1).strip() if match else parameter)
    return types


def _return_type(prefix: str, name: str) -> str:
    prefix = " ".join(prefix.split()).strip()
    if "::" in name and name.split("::")[-1].startswith("~"):
        return "destructor"
    if "::" in name and name.split("::")[-1] == name.split("::")[-2]:
        return "constructor"
    return prefix or "auto"


class CppExtractor(BaseExtractor):
    """Extracteur sans dependance externe pour les signatures C/C++ usuelles."""

    def extract(self, code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
        source = _strip_comments(code)
        functions: List[Dict[str, Any]] = []
        for match in _FUNCTION_RE.finditer(source):
            name = match.group("name")
            short_name = name.split("::")[-1]
            if short_name in _CONTROL_KEYWORDS:
                continue

            body_end = _matching_body_end(source, match.end() - 1)
            node_text = source[match.start():body_end]
            params = _parameter_names(match.group("params"))
            param_types = _parameter_types(match.group("params"))
            return_type = _return_type(match.group("prefix") or "", name)
            is_constructor = return_type == "constructor"
            functions.append({
                "name": name,
                "params": params,
                "param_types": param_types,
                "return_type": return_type,
                "is_async": False,
                "decorators": [],
                "body_hash": hashlib.sha256(node_text.encode("utf-8")).hexdigest(),
                "file": filename,
                "signature": f"{name}({', '.join(params)})" if is_constructor else f"{return_type} {name}({', '.join(params)})",
            })
        return functions

    def supported_extensions(self) -> List[str]:
        return [".c", ".h", ".cc", ".hh", ".cpp", ".cxx", ".hpp"]

    def language_name(self) -> str:
        return "C++"
