from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class InterpreterError(RuntimeError):
    pass


@dataclass(slots=True)
class LanguageSpec:
    """Executable semantics for a small Python-hosted toy language."""

    name: str
    description: str
    semantic_rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "semantic_rules": self.semantic_rules,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LanguageSpec":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            semantic_rules=data.get("semantic_rules", {}),
        )


def default_language_spec() -> LanguageSpec:
    return LanguageSpec(
        name="pynear-v0",
        description="A tiny Python-near expression language interpreted from JSON AST.",
        semantic_rules={
            "truthiness": "python",
            "if_semantics": "normal",
            "comparison_semantics": "normal",
        },
    )


class PythonToyInterpreter:
    """Deterministic Python interpreter for candidate language semantics.

    Program format is JSON AST. This deliberately avoids inventing a parser at
    the start of the project.
    """

    def __init__(self, spec: LanguageSpec | None = None) -> None:
        self.spec = spec or default_language_spec()

    def truthy(self, value: Any) -> bool:
        mode = self.spec.semantic_rules.get("truthiness", "python")
        if mode == "python":
            return bool(value)
        if mode == "inverted":
            return not bool(value)
        if mode == "zero_true":
            is_numeric_zero = isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0
            return is_numeric_zero or bool(value)
        if mode == "empty_true":
            return value in ([], "", {}) or bool(value)
        raise InterpreterError(f"Unknown truthiness rule: {mode}")

    def eval(self, node: dict[str, Any], env: dict[str, Any] | None = None) -> Any:
        env = dict(env or {})
        return self._eval(node, env)

    def _eval(self, node: dict[str, Any], env: dict[str, Any]) -> Any:
        if not isinstance(node, dict) or "type" not in node:
            raise InterpreterError(f"Invalid AST node: {node!r}")
        kind = node["type"]

        if kind == "literal":
            return node.get("value")
        if kind == "var":
            name = node["name"]
            if name not in env:
                raise InterpreterError(f"Unbound variable: {name}")
            return env[name]
        if kind == "let":
            local = dict(env)
            local[node["name"]] = self._eval(node["value"], local)
            return self._eval(node["body"], local)
        if kind == "seq":
            result = None
            local = dict(env)
            for expr in node.get("body", []):
                result = self._eval(expr, local)
            return result
        if kind == "if":
            cond_value = self._eval(node["cond"], env)
            take_then = self.truthy(cond_value)
            if self.spec.semantic_rules.get("if_semantics", "normal") == "inverted":
                take_then = not take_then
            return self._eval(node["then"] if take_then else node["else"], env)
        if kind == "binop":
            left = self._eval(node["left"], env)
            right = self._eval(node["right"], env)
            return self._apply_binop(node["op"], left, right)
        raise InterpreterError(f"Unsupported AST node type: {kind}")

    def _apply_binop(self, op: str, left: Any, right: Any) -> Any:
        comparison_mode = self.spec.semantic_rules.get("comparison_semantics", "normal")
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "==":
            result = left == right
        elif op == "<":
            result = left < right
        elif op == ">":
            result = left > right
        else:
            raise InterpreterError(f"Unsupported binary operator: {op}")
        return not result if comparison_mode == "inverted" else result

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        try:
            actual = self.eval(case["program"], case.get("env"))
            expected = case.get("expected")
            return {
                "case_id": case.get("case_id"),
                "success": actual == expected,
                "actual": actual,
                "expected": expected,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - artifact should preserve failures
            return {
                "case_id": case.get("case_id"),
                "success": False,
                "actual": None,
                "expected": case.get("expected"),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def run_cases(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.run_case(case) for case in cases]
