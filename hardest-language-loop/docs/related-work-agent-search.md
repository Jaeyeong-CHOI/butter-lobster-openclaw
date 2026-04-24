# Related Work Notes: Agentic Search for LLM-Failure Programming Languages

_Last updated: 2026-04-24_

## Why these papers matter

This project is closest to a hybrid of:

1. **LLM-guided evolutionary/program search**: use an LLM as a mutation/proposal operator, then score candidates with a deterministic evaluator.
2. **Language-agent tree search / reflection**: keep search state, feedback, and self-reflection across iterations.
3. **Automated benchmark/red-team generation**: generate tasks that expose model weaknesses rather than solve a fixed benchmark.
4. **Programming-language semantics robustness**: test whether models follow explicit semantics or fall back to Python/C-like priors.

The strongest framing is not “generate random weird languages”, but:

> **Hypothesis-driven, quality-diverse search over near-familiar programming-language semantics, scored by reproducible solver failure under deterministic validators.**

---

## Most relevant systems and papers

### 1) LLM-guided program/evolutionary search

#### FunSearch — _Mathematical discoveries from program search with large language models_ (Nature, 2023)
- URL: https://www.nature.com/articles/s41586-023-06924-6
- Core idea: frozen LLM proposes programs; evaluator scores them; top programs are fed back into later prompts; island-based evolutionary search maintains diversity.
- Key relevance: this is the closest structural ancestor. Our evaluator is not “solution quality”, but **model failure rate under a candidate language**.
- Takeaway: keep an archive, sample strong/diverse candidates into prompts, and score with deterministic execution.

#### Evolution through Large Models (ELM) (arXiv:2206.08896)
- URL: https://arxiv.org/abs/2206.08896
- Core idea: code LLMs can serve as learned mutation operators inside genetic programming / MAP-Elites style search.
- Key relevance: language-designer agent should not only invent from scratch; it should mutate high-value prior language specs.
- Takeaway: implement explicit mutation operators plus LLM-guided mutation, not pure free-form generation.

#### ReEvo — _Large Language Models as Hyper-Heuristics with Reflective Evolution_ (NeurIPS 2024, arXiv:2402.01145)
- URL: https://arxiv.org/abs/2402.01145
- Core idea: evolutionary search plus LLM reflections as “verbal gradients” for heuristic design.
- Key relevance: after each evaluation batch, a curator should write a structured reflection: what failed, why, and what mutation to try next.
- Takeaway: add a reflection artifact per strategy node, then use it to condition child generation.

#### LLMatic — _Neural Architecture Search via LLMs and Quality Diversity Optimization_ (GECCO 2024, arXiv:2306.01102)
- URL: https://arxiv.org/abs/2306.01102
- Core idea: LLM proposes code variations; quality-diversity algorithms maintain diverse, high-performing candidates.
- Key relevance: a single “best failure rate” can collapse into trivial adversarial languages. We need diversity niches.
- Takeaway: track niches such as semantic family, Python distance, failure mode, and affected problem type.

#### In-context QD — _Large Language Models as In-context AI Generators for Quality-Diversity_ (arXiv:2404.15794)
- URL: https://arxiv.org/abs/2404.15794
- Core idea: prompt the model with many examples from a quality-diverse archive so it can recombine them.
- Key relevance: language designer prompts should include compact exemplars from several branches, not only the current best node.
- Takeaway: implement archive sampling: top-k by score + diverse-k by niche + recent failure reflections.

#### FunBO — _Discovering Acquisition Functions for Bayesian Optimization with FunSearch_ (arXiv:2406.04824)
- URL: https://arxiv.org/abs/2406.04824
- Core idea: FunSearch-like loop can discover reusable code artifacts that generalize beyond the training functions.
- Key relevance: candidate languages should be evaluated for generalization across held-out problem families, not just current benchmark tasks.
- Takeaway: separate public exploration problems from hidden/generalization problems.

#### AlphaTensor — _Discovering faster matrix multiplication algorithms with reinforcement learning_ (Nature, 2022)
- URL: https://www.nature.com/articles/s41586-022-05172-4
- Core idea: formalize algorithm discovery as a game with a verifiable reward.
- Key relevance: not LLM-agent work, but useful for research framing: machine search can discover algorithmic artifacts when the evaluator is rigorous.
- Takeaway: emphasize the validator as the scientific anchor.

#### AlphaCode — _Competition-Level Code Generation with AlphaCode_ (Science/arXiv:2203.07814)
- URL: https://arxiv.org/abs/2203.07814
- Core idea: large-scale sampling plus behavioral filtering is crucial for competitive programming.
- Key relevance: solver failure should be measured after allowing reasonable sampling/retry policies, otherwise results may overstate weakness.
- Takeaway: report solver budget explicitly: temperature, repeats, hidden tests, timeout, parse failures.

---

### 2) Language-agent planning, reflection, and tree search

#### Tree of Thoughts (ToT) — _Deliberate Problem Solving with Large Language Models_ (NeurIPS 2023, arXiv:2305.10601)
- URL: https://arxiv.org/abs/2305.10601
- Core idea: search over coherent intermediate “thought” states with self-evaluation and backtracking.
- Key relevance: our strategy tree is analogous, but nodes are language hypotheses rather than reasoning steps.
- Takeaway: support branching, node scoring, backtracking, and expansion from non-best but promising branches.

#### LATS — _Language Agent Tree Search Unifies Reasoning Acting and Planning_ (arXiv:2310.04406)
- URL: https://arxiv.org/abs/2310.04406
- Core idea: integrate Monte Carlo Tree Search, LM value functions, self-reflection, and environment feedback.
- Key relevance: our loop has an environment: interpreter + solver benchmark + validator.
- Takeaway: a future version can use UCB/MCTS-style selection over language nodes, not just greedy failure rate.

#### RF-Agent — _Automated Reward Function Design via Language Agent Tree Search_ (arXiv:2602.23876)
- URL: https://arxiv.org/abs/2602.23876
- Core idea: treats reward-function design as sequential decision-making and uses MCTS to exploit historical feedback more efficiently.
- Key relevance: very close structurally: we design language semantics instead of reward functions, but both are executable artifacts optimized through feedback.
- Takeaway: add MCTS/UCB-style node selection once the archive has enough evaluated candidates.

#### Reflexion — _Language Agents with Verbal Reinforcement Learning_ (arXiv:2303.11366)
- URL: https://arxiv.org/abs/2303.11366
- Core idea: agents improve through natural-language reflections stored in episodic memory rather than weight updates.
- Key relevance: store per-node reflections and pass them into the next language-designer prompt.
- Takeaway: reflection should be structured and reusable: failure hypothesis, counterexample, mutation proposal.

#### Self-Refine — _Iterative Refinement with Self-Feedback_ (arXiv:2303.17651)
- URL: https://arxiv.org/abs/2303.17651
- Core idea: generate, critique, revise without external fine-tuning.
- Key relevance: use designer → critic/curator → revised candidate before spending full solver benchmark budget.
- Takeaway: cheap pre-screening can catch malformed or uninteresting language specs.

#### Eureka — _Human-Level Reward Design via Coding Large Language Models_ (ICLR 2024, arXiv:2310.12931)
- URL: https://arxiv.org/abs/2310.12931
- Core idea: LLM evolves reward code using environment feedback.
- Key relevance: the language designer is analogous to reward designer; both generate code/specs whose quality is only known after execution.
- Takeaway: let the agent write compact explanatory rationales, but judge only by executable evaluation.

#### Voyager — _An Open-Ended Embodied Agent with Large Language Models_ (arXiv:2305.16291)
- URL: https://arxiv.org/abs/2305.16291
- Core idea: automatic curriculum, skill library, iterative prompting with execution errors and self-verification.
- Key relevance: we need a “language library” of reusable semantic perturbations and failure motifs.
- Takeaway: build a skill/spec library: `truthiness`, `comparison`, `binding`, `short-circuit`, `scope`, `empty value`, etc.

---

### 3) Multi-agent software-development agents

#### SWE-agent — _Agent-Computer Interfaces Enable Automated Software Engineering_ (arXiv:2405.15793)
- URL: https://arxiv.org/abs/2405.15793
- Core idea: agent-computer interface design strongly affects agent performance in coding tasks.
- Key relevance: if solver agents receive an awkward DSL/interface, failures may reflect interface friction rather than semantic weakness.
- Takeaway: keep solver interface stable, explicit, and auditable. Measure parse/interface errors separately from semantic errors.

#### MetaGPT — _Meta Programming for A Multi-Agent Collaborative Framework_ (arXiv:2308.00352)
- URL: https://arxiv.org/abs/2308.00352
- Core idea: structured roles and SOPs reduce cascading hallucination in multi-agent systems.
- Key relevance: our designer/solver/curator roles should have strict I/O contracts and separate artifacts.
- Takeaway: keep current separate Python files and JSON schemas; avoid free-form agent chatter as state.

#### ChatDev — _Communicative Agents for Software Development_ (ACL 2024, arXiv:2307.07924)
- URL: https://arxiv.org/abs/2307.07924
- Core idea: specialized agents communicate through controlled chat chains and debugging dialogues.
- Key relevance: useful as background, but less central than FunSearch/ReEvo/LATS because our loop needs hard evaluator feedback more than dialogue.
- Takeaway: multi-agent communication should be minimal and logged; the validator should settle disagreements.

---

### 4) Automated benchmark and red-team generation

#### Hypothesis-driven hard problem generation — _Automatically Generating Hard Math Problems from Hypothesis-Driven Error Analysis_ (arXiv:2604.04386)
- URL: https://arxiv.org/abs/2604.04386
- Core idea: generate hypotheses about model weaknesses, then generate benchmark items targeting those weaknesses.
- Key relevance: very close framing: our “weakness hypotheses” are semantic perturbations, and our benchmark items are implementation problems.
- Takeaway: make each language node explicitly state a failure hypothesis before evaluation.

#### Automated Progressive Red Teaming (APRT) (COLING 2025, arXiv:2407.03876)
- URL: https://arxiv.org/abs/2407.03876
- Core idea: progressively generate and filter adversarial prompts with diversity and effectiveness tracking.
- Key relevance: our loop is a non-safety red-team for code semantics.
- Takeaway: maintain both attack effectiveness/failure rate and diversity; filter ineffective or duplicate candidates early.

#### Red Teaming Language Models with Language Models (arXiv:2202.03286)
- URL: https://arxiv.org/abs/2202.03286
- Core idea: use one LM to automatically generate test cases that expose harmful or undesirable behavior in another LM.
- Key relevance: establishes the broader “model-generated adversarial evaluation” pattern that our project applies to programming-language semantics.
- Takeaway: report diversity and difficulty of generated cases, not only raw failure counts.

#### AutoBencher — _Towards Declarative Benchmark Construction_ (ICLR 2025, arXiv:2407.08351)
- URL: https://arxiv.org/abs/2407.08351
- Core idea: declare benchmark desiderata such as difficulty or salience, then iteratively optimize dataset descriptions and generated questions.
- Key relevance: our language-generation objective can be stated declaratively: find Python-near semantics that induce reproducible, interpretable solver failures.
- Takeaway: add explicit benchmark desiderata to the language-designer prompt: difficulty, novelty, interpretability, and non-triviality.

#### Diverse Prompts / MAP-Elites — _Illuminating the Prompt Space of LLMs with MAP-Elites_ (arXiv:2504.14367)
- URL: https://arxiv.org/abs/2504.14367
- Core idea: use grammar + MAP-Elites to map prompt structure against performance.
- Key relevance: similar archive logic applies to language-spec structure.
- Takeaway: define behavioral descriptors for languages and search niches, not just scalar score.

---

### 5) Code generation robustness and programming-language semantics

#### PLSemanticsBench — _Large Language Models As Programming Language Interpreters_ (arXiv:2510.03415)
- URL: https://arxiv.org/abs/2510.03415
- Core idea: evaluate whether models can execute programs from formal semantics; includes standard and systematically mutated semantics; performance drops under nonstandard semantics.
- Key relevance: probably the closest PL-semantics benchmark paper. It supports our central claim that models lack robust semantics understanding under mutated rules.
- Takeaway: add evaluation modes beyond synthesis: final-state prediction, rule prediction, and execution-trace prediction.

#### EquiBench — _Benchmarking LLMs' Reasoning about Program Semantics via Equivalence Checking_ (arXiv:2502.12466)
- URL: https://arxiv.org/abs/2502.12466
- Core idea: asks whether two programs are semantically equivalent across inputs; finds models often rely on syntactic similarity rather than robust semantic reasoning.
- Key relevance: gives us another task family besides “write a program”: equivalence checking under altered semantics.
- Takeaway: add candidate-language equivalence tasks, especially pairs that look syntactically similar but diverge under custom semantics.

#### Program Semantic Inequivalence Game with Large Language Models (arXiv:2505.03818)
- URL: https://arxiv.org/abs/2505.03818
- Core idea: a generator creates semantically distinct program variants while an evaluator searches for inputs that expose divergent behavior.
- Key relevance: this is a near match to our adversarial loop, except our variants are language-semantics changes rather than program variants.
- Takeaway: add a second adversary that searches for discriminating test inputs for each candidate language.

#### REval — _Reasoning Runtime Behavior of a Program with LLM: How Far Are We?_ (ICSE 2025, arXiv:2403.16437)
- URL: https://arxiv.org/abs/2403.16437
- Core idea: evaluates runtime behavior reasoning and incremental consistency during program execution, not just final I/O.
- Key relevance: supports adding trace-level benchmark modes; a solver may get the final output right while reasoning under the wrong semantics.
- Takeaway: store execution-trace predictions and consistency checks for top candidate languages.

#### CodeCrash — _Exposing LLM Fragility to Misleading Natural Language in Code Reasoning_ (NeurIPS 2025, arXiv:2504.14119)
- URL: https://arxiv.org/abs/2504.14119
- Core idea: evaluates robustness of code reasoning under structural perturbations and misleading natural-language context; models over-rely on plausible but wrong cues.
- Key relevance: our prompts may accidentally help or mislead solvers through wording; we need controls for prompt phrasing and distracting hints.
- Takeaway: add paraphrase/misleading-context controls to separate true semantic understanding from prompt-cue reliance.

#### Syntactic Robustness for LLM-based Code Generation (arXiv:2404.01535)
- URL: https://arxiv.org/abs/2404.01535
- Core idea: semantically equivalent prompt/formula rewrites can cause code-generation changes.
- Key relevance: shows surface-form brittleness; our work targets semantic-prior brittleness.
- Takeaway: include prompt paraphrase controls so observed failures are not just wording artifacts.

#### Multi-language Robustness of LLM Code Generation (arXiv:2504.19108)
- URL: https://arxiv.org/abs/2504.19108
- Core idea: performance degrades under docstring/function/syntax/format perturbations across languages; semantic perturbations are especially disruptive.
- Key relevance: reinforces that robustness varies by language and perturbation type.
- Takeaway: compare Python-near DSL against multiple surface syntaxes later.

#### Adversarial Attack Classification and Robustness Testing for LLMs for Code (arXiv:2506.07942)
- URL: https://arxiv.org/abs/2506.07942
- Core idea: taxonomy of attacks on code-generation models by input type and perturbation granularity.
- Key relevance: helps classify our perturbations as semantic-level adversarial tests rather than character/word/syntax attacks.
- Takeaway: define a taxonomy of semantic attacks: operator inversion, truthiness shift, binding/scope shift, evaluation-order shift, emptiness/nullability shift.

#### LLMorpheus — _Mutation Testing using Large Language Models_ (arXiv:2404.09952)
- URL: https://arxiv.org/abs/2404.09952
- Core idea: LLM-generated mutants can resemble real bugs beyond fixed mutation operators.
- Key relevance: language semantics mutations can be treated similarly to mutants, but the “program under test” is the solver model.
- Takeaway: combine fixed semantic mutation templates with LLM-generated novel mutations.

---

## Design implications for this project

### A. The strategy tree should become a quality-diversity archive

Current tree scoring by failure rate is useful, but the literature suggests adding **niches/descriptors**:

- semantic family: truthiness / comparison / arithmetic / scope / control-flow / evaluation order / collection semantics
- Python distance: near / medium / far
- explicitness: rule stated directly / example-only / interpreter-only
- failure mode: parse failure / hidden-test semantic error / public-test overfit / timeout / refusal / prior-dominance
- affected task family: numeric / branching / empty-value / nested control / data-structure

This prevents the loop from converging only to obvious inverted-comparison languages.

### B. Add a curator reflection artifact after every evaluation batch

Inspired by ReEvo and Reflexion, each node should store something like:

```json
{
  "failure_hypothesis": "Model applies Python comparison priors despite inverted spec.",
  "evidence": ["gpt-4o failed max-two and clamp-0-10", "gpt-5.4 recovered on simple abs-int"],
  "next_mutations": [
    "combine inverted comparison with non-Python truthiness",
    "hide comparison inversion behind examples only",
    "add nested conditional problems"
  ]
}
```

Use these reflections as prompt context for child generation.

### C. Use FunSearch-style archive sampling for designer prompts

Instead of prompting with only the best current node, sample:

- top scored candidates,
- diverse candidates from different niches,
- recent candidates with surprising model splits,
- failed/invalid candidates as negative examples.

This should improve novelty while preserving useful discoveries.

### D. Separate solver failure from interface failure

SWE-agent and ACI work makes this important. Track separately:

- prompt misunderstood,
- invalid JSON AST,
- valid AST but wrong behavior,
- public tests passed but hidden failed,
- timeout/runtime error,
- refusal/API issue.

Only semantic wrong behavior should count as the cleanest evidence of LLM semantic weakness.

### E. Add more benchmark modes, not only implementation synthesis

PLSemanticsBench suggests adding:

1. final-state prediction,
2. semantic-rule prediction,
3. execution-trace prediction,
4. program synthesis / implementation.

This helps distinguish “cannot write program in DSL” from “cannot mentally execute nonstandard semantics”.

### F. Keep deterministic validators and hidden tests central

Across FunSearch, AlphaCode, Eureka, and AlphaTensor, the scientific value comes from verifiable evaluation. For our project:

- deterministic Python interpreter is the ground truth,
- public/hidden tests must be separated,
- results must include model, temperature, repeats, prompt hash, language hash, and problem hash,
- infra/API errors must not count as solver failures.

### G. The research story should explicitly connect to automated red teaming

A strong framing:

> We perform automated red-teaming of code LLMs in the space of programming-language semantics. Instead of adversarial prompts, we generate adversarial-but-executable language semantics and measure robust semantic adherence.

This connects the project to both PL and AI-safety/evaluation communities.

---

## Suggested next implementation changes

1. Add `niche_descriptors` and `failure_modes` to `StrategyNode.metrics` or artifacts.
2. Add `curator_reflection.json` per node after each evaluation batch.
3. Add QD-style frontier selection: `score + novelty_bonus + uncertainty_bonus`.
4. Add prompt paraphrase controls for top candidates.
5. Add final-state / trace-prediction benchmark modes before expanding to many more languages.
6. Add a held-out problem split and report public-vs-hidden generalization.
7. Add automatic related-work links in generated run reports so results map back to these research themes.
