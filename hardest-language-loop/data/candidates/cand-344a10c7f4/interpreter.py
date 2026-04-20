# interpreter.py for PL-025 L1
# This code defines the programming language used for evaluation.

class CandidateLanguage:
    name = 'PL-025 L1'
    level = 'L1'

# Token-conflict language: parser rewrites conflicting keywords before evaluation
KEYWORD_MAP = {'fn': 'def', 'unless': 'if', 'yieldback': 'return'}


def run_program(source: str, tests: list[dict]) -> dict:
    # TODO: replace with real parser + executor.
    # Current MVP keeps the contract fixed for later integration.
    return {
        'ok': True,
        'candidate': 'cand-344a10c7f4',
        'note': 'MVP interpreter stub; connect real semantics here.'
    }
