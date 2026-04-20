# interpreter.py for PL-021 L2
# This code defines the programming language used for evaluation.

class CandidateLanguage:
    name = 'PL-021 L2'
    level = 'L2'

# Syntax-conflict language: blocks and declarations are reshaped before execution
# Example: :define name [args] ->  becomes  def name(args):


def run_program(source: str, tests: list[dict]) -> dict:
    # TODO: replace with real parser + executor.
    # Current MVP keeps the contract fixed for later integration.
    return {
        'ok': True,
        'candidate': 'cand-3e90d00011',
        'note': 'MVP interpreter stub; connect real semantics here.'
    }
