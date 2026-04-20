# interpreter.py for PL-022 L3
# This code defines the programming language used for evaluation.

class CandidateLanguage:
    name = 'PL-022 L3'
    level = 'L3'

# Semantic-conflict language: conditionals execute when condition is FALSE
def eval_if(cond: bool) -> bool:
    return not cond


def run_program(source: str, tests: list[dict]) -> dict:
    # TODO: replace with real parser + executor.
    # Current MVP keeps the contract fixed for later integration.
    return {
        'ok': True,
        'candidate': 'cand-8c9eb09f5e',
        'note': 'MVP interpreter stub; connect real semantics here.'
    }
