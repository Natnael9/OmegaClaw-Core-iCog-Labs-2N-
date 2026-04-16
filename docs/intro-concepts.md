# Core Concepts

Vocabulary used throughout the rest of the documentation. Skim once; come back when a term shows up in another page.

---

## Hybrid reasoning

LLM + formal logic engine, operated as one pipeline. The LLM handles language and orchestration; the engine handles truth-value arithmetic. See [intro-hybrid-reasoning.md](./intro-hybrid-reasoning.md).

## AtomSpace

The knowledge substrate provided by Hyperon / MeTTa. Every fact, memory item, and program fragment in OmegaClaw lives in the same AtomSpace, so memory is directly interrogable by other Hyperon components.

## Atomization

The act of converting natural-language facts into AtomSpace atoms with explicit truth values. Example:

Natural: *"Sam and Garfield are friends, and Garfield is an animal."*

Atomized:

```metta
(--> (× sam garfield) friend)  (stv 1.0 0.9)
(--> garfield animal)          (stv 1.0 0.9)
```

Atomization is a first-class step — raw text cannot participate in formal inference. Each atom carries an **explicit relationship type** (inheritance, implication, similarity) and an **explicit truth value**.

## `stv` — subjective truth value

Every atom carries `(stv frequency confidence)`:

- **frequency** ∈ [0.0, 1.0] — how often the statement held among observed evidence.
- **confidence** ∈ [0.0, 1.0] — how much evidence we have.

Negation is `(stv 0.0 c)` — strong evidence *against* the statement.

## Expectation

A scalar derived from `(stv f c)`:

```
exp = c × (f - 0.5) + 0.5
```

Maps an `(f, c)` pair to a single value in `[0, 1]`, useful for priority queues and ranking.

## The reasoning engines

| Engine | MeTTa operator | Strength |
|---|---|---|
| **NAL** — Non-Axiomatic Logic | `\|-` | Symbolic inference under uncertainty, revision, evidence merging |
| **PLN** — Probabilistic Logic Networks | `\|~` | Probabilistic higher-order reasoning |

ONA (OpenNARS for Applications) is a planned third engine for real-time temporal reasoning but is **not installed by default** — see [reference-lib-ona.md](./reference-lib-ona.md) for the current experimental status.

Dedicated pages: [reference-lib-nal.md](./reference-lib-nal.md), [reference-lib-pln.md](./reference-lib-pln.md), [reference-lib-ona.md](./reference-lib-ona.md) (experimental, not installed).

## Orchestration

The LLM's policy for picking which engine (or no engine) to invoke for a given task, plus when to stop reasoning. Full table in [reference-orchestration.md](./reference-orchestration.md).

## Three-tier memory

Three distinct stores with different semantics:

1. **Working memory (`pin`)** — volatile single-slot scratchpad. Overwritten each cycle.
2. **Long-term embedding memory (`remember` / `query`)** — persistent semantic recall. Survives restarts.
3. **AtomSpace** — atomized, truth-valued knowledge used by NAL and PLN.

Full detail in [reference-internals-memory-store.md](./reference-internals-memory-store.md).

## Skills

The set of callable operations available to the agent at each turn — plain MeTTa s-expressions like `(remember "...")`, `(shell "ls")`, `(metta (|- ...))`. Defined in `src/skills.metta` and `src/memory.metta`.

## Channels

Abstract communication endpoints. `(send ...)` and `(receive)` delegate to the active channel adapter (IRC or Mattermost by default). See [reference-channels.md](./reference-channels.md).

## Agentic loop

The main control cycle in `src/loop.metta`: build prompt → call LLM → parse skill s-expressions → execute → append results to episodic trace → sleep → repeat. See [intro-architecture.md](./intro-architecture.md).

## Action thresholds

Three decision tiers applied to any `(f, c)` before acting on the conclusion:

| Tier | Gate |
|---|---|
| ACT | `f ≥ 0.6 AND c ≥ 0.5` |
| HYPOTHESIZE | `f ≥ 0.3 AND c ≥ 0.2` |
| IGNORE | below |

Full context in [reference-orchestration.md](./reference-orchestration.md).

## The defense stack

Four layers applied to every piece of incoming evidence to resist noise and adversarial input:

1. **Novelty modulation** — new claims enter with `c × (1 − novelty)`.
2. **Action thresholds** — the tiers above.
3. **Attention budgeting** — priority queue by expectation, with per-cycle step limits.
4. **Adversarial premise testing** — regression suite for confident lies, contradictions, and gradual poisoning.

See [reference-orchestration.md](./reference-orchestration.md) for each layer.

## External grounding

The pattern of anchoring a premise's confidence on a verified external source rather than the LLM's prior. The primary mitigation for premise-formulation errors. See [tutorial-08-grounded-reasoning.md](./tutorial-08-grounded-reasoning.md).

## Revision

An inference rule that merges independent evidence about the same statement. Increases confidence when sources agree; produces a middle frequency with high confidence when they disagree, making contradiction visible.

## GIGO amplification

The failure mode where a flawed premise is run through the formal engine and emerges with a mathematically-authoritative-looking conclusion. Why the mitigations matter. See [reference-failure-modes.md](./reference-failure-modes.md).

## Agentverse-backed skill

A skill whose implementation is a remote agent reached through the Agentverse bridge rather than a local function. See [tutorial-07-remote-agentverse-skills.md](./tutorial-07-remote-agentverse-skills.md).
