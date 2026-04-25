from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .interpreter import LanguageSpec, PythonToyInterpreter


@dataclass(frozen=True, slots=True)
class TestCase:
    case_id: str
    env: dict[str, Any]
    expected: Any
    public: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ImplementationProblem:
    """A task the solver must implement in the candidate language.

    The solver receives the instruction, input variables, and public examples.
    It must return one JSON-AST program. The validator runs that program across
    public + hidden test cases under the candidate language semantics.
    """

    problem_id: str
    title: str
    language_spec: LanguageSpec
    instruction: str
    inputs: list[str]
    public_examples: list[TestCase]
    hidden_tests: list[TestCase]
    reference_program: dict[str, Any]
    expected_failure_mode: str
    tags: list[str]

    @property
    def all_tests(self) -> list[TestCase]:
        return [*self.public_examples, *self.hidden_tests]

    def to_solver_task(self) -> dict[str, Any]:
        return {
            "task_id": self.problem_id,
            "title": self.title,
            "instruction": self.instruction,
            "inputs": self.inputs,
            "public_examples": [case.to_dict() for case in self.public_examples],
            "response_goal": "Return one JSON AST program that computes the expected output for all tests.",
            "expected_failure_mode": self.expected_failure_mode,
            "tags": self.tags,
        }

    def interpreter_cases_for(self, program: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "case_id": case.case_id,
                "program": program,
                "env": case.env,
                "expected": case.expected,
            }
            for case in self.all_tests
        ]

    def validate_reference(self) -> list[dict[str, Any]]:
        return PythonToyInterpreter(self.language_spec).run_cases(self.interpreter_cases_for(self.reference_program))

    def to_dict(self, *, include_reference: bool = True, include_hidden: bool = True) -> dict[str, Any]:
        data = {
            "problem_id": self.problem_id,
            "title": self.title,
            "language_spec": self.language_spec.to_dict(),
            "instruction": self.instruction,
            "inputs": self.inputs,
            "public_examples": [case.to_dict() for case in self.public_examples],
            "expected_failure_mode": self.expected_failure_mode,
            "tags": self.tags,
        }
        if include_hidden:
            data["hidden_tests"] = [case.to_dict() for case in self.hidden_tests]
        if include_reference:
            data["reference_program"] = self.reference_program
        return data


# Tiny JSON-AST builders keep reference programs readable.
def lit(value: Any) -> dict[str, Any]:
    return {"type": "literal", "value": value}


def var(name: str) -> dict[str, Any]:
    return {"type": "var", "name": name}


def binop(op: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {"type": "binop", "op": op, "left": left, "right": right}


def iff(cond: dict[str, Any], then: dict[str, Any], otherwise: dict[str, Any]) -> dict[str, Any]:
    return {"type": "if", "cond": cond, "then": then, "else": otherwise}


def default_language_spec() -> LanguageSpec:
    return LanguageSpec(
        name="pynear-empty-true-v0",
        description=(
            "Python-near JSON-AST language. Arithmetic/comparison are Python-like, "
            "but empty strings/lists/dicts are truthy."
        ),
        semantic_rules={
            "truthiness": "empty_true",
            "if_semantics": "normal",
            "comparison_semantics": "normal",
            "arithmetic_semantics": "normal",
            "literal_semantics": "normal",
        },
    )


def default_problem_set(language_spec: LanguageSpec | None = None) -> list[ImplementationProblem]:
    spec = language_spec or default_language_spec()
    return [
        ImplementationProblem(
            problem_id="abs-int",
            title="Absolute Value",
            language_spec=spec,
            instruction="Given integer x, return its absolute value.",
            inputs=["x"],
            public_examples=[
                TestCase("abs-public-neg", {"x": -3}, 3, public=True),
                TestCase("abs-public-pos", {"x": 4}, 4, public=True),
            ],
            hidden_tests=[
                TestCase("abs-hidden-zero", {"x": 0}, 0),
                TestCase("abs-hidden-one-neg", {"x": -1}, 1),
                TestCase("abs-hidden-one-pos", {"x": 1}, 1),
                TestCase("abs-hidden-large-neg", {"x": -12}, 12),
                TestCase("abs-hidden-large-pos", {"x": 99}, 99),
                TestCase("abs-hidden-very-large-neg", {"x": -1000}, 1000),
            ],
            reference_program=iff(binop("<", var("x"), lit(0)), binop("-", lit(0), var("x")), var("x")),
            expected_failure_mode="Basic control-flow sanity task; should fail only if solver mishandles conditionals.",
            tags=["baseline", "branching", "arithmetic"],
        ),
        ImplementationProblem(
            problem_id="max-two",
            title="Maximum of Two Integers",
            language_spec=spec,
            instruction="Given integers a and b, return the larger value. If tied, return a.",
            inputs=["a", "b"],
            public_examples=[
                TestCase("max-public-a", {"a": 7, "b": 2}, 7, public=True),
                TestCase("max-public-b", {"a": -1, "b": 5}, 5, public=True),
            ],
            hidden_tests=[
                TestCase("max-hidden-tie-positive", {"a": 4, "b": 4}, 4),
                TestCase("max-hidden-tie-negative", {"a": -4, "b": -4}, -4),
                TestCase("max-hidden-negative", {"a": -8, "b": -3}, -3),
                TestCase("max-hidden-mixed-left", {"a": 0, "b": -1}, 0),
                TestCase("max-hidden-mixed-right", {"a": -1, "b": 0}, 0),
                TestCase("max-hidden-large", {"a": 123, "b": 122}, 123),
            ],
            reference_program=iff(binop(">", var("a"), var("b")), var("a"), var("b")),
            expected_failure_mode="Baseline comparison task; useful for detecting accidental comparison-rule confusion.",
            tags=["baseline", "comparison"],
        ),
        ImplementationProblem(
            problem_id="clamp-0-10",
            title="Clamp to [0, 10]",
            language_spec=spec,
            instruction="Given integer x, return 0 if x < 0, 10 if x > 10, otherwise return x.",
            inputs=["x"],
            public_examples=[
                TestCase("clamp-public-low", {"x": -2}, 0, public=True),
                TestCase("clamp-public-mid", {"x": 6}, 6, public=True),
                TestCase("clamp-public-high", {"x": 14}, 10, public=True),
            ],
            hidden_tests=[
                TestCase("clamp-hidden-zero", {"x": 0}, 0),
                TestCase("clamp-hidden-ten", {"x": 10}, 10),
                TestCase("clamp-hidden-one", {"x": 1}, 1),
                TestCase("clamp-hidden-nine", {"x": 9}, 9),
                TestCase("clamp-hidden-low-boundary", {"x": -1}, 0),
                TestCase("clamp-hidden-high-boundary", {"x": 11}, 10),
                TestCase("clamp-hidden-very-low", {"x": -100}, 0),
                TestCase("clamp-hidden-high", {"x": 99}, 10),
            ],
            reference_program=iff(
                binop("<", var("x"), lit(0)),
                lit(0),
                iff(binop(">", var("x"), lit(10)), lit(10), var("x")),
            ),
            expected_failure_mode="Nested-branch baseline; exposes shallow one-branch solutions.",
            tags=["baseline", "nested-branch"],
        ),
        ImplementationProblem(
            problem_id="sign-bucket",
            title="Sign Bucket",
            language_spec=spec,
            instruction="Given integer x, return -1 if x < 0, 0 if x == 0, and 1 otherwise.",
            inputs=["x"],
            public_examples=[
                TestCase("sign-public-neg", {"x": -9}, -1, public=True),
                TestCase("sign-public-zero", {"x": 0}, 0, public=True),
                TestCase("sign-public-pos", {"x": 2}, 1, public=True),
            ],
            hidden_tests=[
                TestCase("sign-hidden-neg-one", {"x": -1}, -1),
                TestCase("sign-hidden-neg-large", {"x": -100}, -1),
                TestCase("sign-hidden-pos-one", {"x": 1}, 1),
                TestCase("sign-hidden-pos-large", {"x": 100}, 1),
                TestCase("sign-hidden-zero-repeat", {"x": 0}, 0),
            ],
            reference_program=iff(
                binop("<", var("x"), lit(0)),
                lit(-1),
                iff(binop("==", var("x"), lit(0)), lit(0), lit(1)),
            ),
            expected_failure_mode="Multi-way branching; catches models that collapse equality and ordering cases.",
            tags=["baseline", "multi-way"],
        ),
        ImplementationProblem(
            problem_id="empty-token-bonus",
            title="Empty Token Bonus",
            language_spec=spec,
            instruction=(
                "Given token and score, return score + 10 when token is truthy under the candidate language; "
                "otherwise return score - 10."
            ),
            inputs=["token", "score"],
            public_examples=[
                TestCase("bonus-public-nonempty", {"token": "ok", "score": 5}, 15, public=True),
                TestCase("bonus-public-false", {"token": False, "score": 5}, -5, public=True),
            ],
            hidden_tests=[
                TestCase("bonus-hidden-empty-string", {"token": "", "score": 5}, 15),
                TestCase("bonus-hidden-empty-list", {"token": [], "score": 1}, 11),
                TestCase("bonus-hidden-empty-dict", {"token": {}, "score": -2}, 8),
                TestCase("bonus-hidden-zero", {"token": 0, "score": 1}, -9),
                TestCase("bonus-hidden-none", {"token": None, "score": 3}, -7),
                TestCase("bonus-hidden-nonempty-list", {"token": [1], "score": 0}, 10),
                TestCase("bonus-hidden-true-negative-score", {"token": True, "score": -5}, 5),
                TestCase("bonus-hidden-false-negative-score", {"token": False, "score": -5}, -15),
            ],
            reference_program=iff(var("token"), binop("+", var("score"), lit(10)), binop("-", var("score"), lit(10))),
            expected_failure_mode=(
                "Python prior treats empty string/list as false, but this candidate language treats them as true."
            ),
            tags=["semantic-prior-trap", "truthiness"],
        ),
        ImplementationProblem(
            problem_id="empty-guarded-select",
            title="Empty Guarded Select",
            language_spec=spec,
            instruction=(
                "Given guard, left, and right, return left when guard is truthy under the candidate language; "
                "otherwise return right."
            ),
            inputs=["guard", "left", "right"],
            public_examples=[
                TestCase("select-public-true", {"guard": True, "left": 3, "right": 8}, 3, public=True),
                TestCase("select-public-false", {"guard": False, "left": 3, "right": 8}, 8, public=True),
            ],
            hidden_tests=[
                TestCase("select-hidden-empty-string", {"guard": "", "left": 3, "right": 8}, 3),
                TestCase("select-hidden-empty-list", {"guard": [], "left": 4, "right": 8}, 4),
                TestCase("select-hidden-empty-dict", {"guard": {}, "left": -1, "right": 9}, -1),
                TestCase("select-hidden-zero", {"guard": 0, "left": -1, "right": 9}, 9),
                TestCase("select-hidden-none", {"guard": None, "left": 1, "right": 2}, 2),
                TestCase("select-hidden-nonempty-string", {"guard": "x", "left": 10, "right": 20}, 10),
                TestCase("select-hidden-nonempty-list", {"guard": [0], "left": -10, "right": -20}, -10),
                TestCase("select-hidden-true", {"guard": True, "left": 7, "right": 9}, 7),
            ],
            reference_program=iff(var("guard"), var("left"), var("right")),
            expected_failure_mode="Direct truthiness trap with hidden empty-value cases.",
            tags=["semantic-prior-trap", "truthiness", "hidden-cases"],
        ),
    ]


def default_problem() -> ImplementationProblem:
    return default_problem_set()[4]


def validate_problem_set(problems: list[ImplementationProblem] | None = None) -> list[dict[str, Any]]:
    problems = problems or default_problem_set()
    summary: list[dict[str, Any]] = []
    for problem in problems:
        results = problem.validate_reference()
        summary.append(
            {
                "problem_id": problem.problem_id,
                "title": problem.title,
                "num_tests": len(results),
                "success": all(result["success"] for result in results),
                "results": results,
            }
        )
    return summary
