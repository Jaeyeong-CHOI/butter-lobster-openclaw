# interpreter.py for PL-024 L5
# This code defines the programming language used for evaluation.

class CandidateLanguage:
    name = 'PL-024 L5'
    level = 'L5'

# Compound conflict language: keyword remap + syntax reshape + inverted conditionals
KEYWORD_MAP = {'fn': 'def', 'give': 'return'}
def eval_if(cond: bool) -> bool:
    return not cond


def run_program(source: str, tests: list[dict]) -> dict:
    # TODO: replace with real parser + executor.
    # Current MVP keeps the contract fixed for later integration.
    return {
        'ok': True,
        'candidate': 'cand-a96b9d97ac',
        'note': 'MVP interpreter stub; connect real semantics here.'
    }
