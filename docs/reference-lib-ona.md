# Reference — ONA (OpenNARS for Applications)

ONA is a lightweight, real-time implementation of NARS created by Dr. Patrick Hammer. It is the third reasoning engine available to OmegaClaw, complementing symbolic NAL (`|-`) and probabilistic PLN (`|~`).

## What ONA adds

- **Throughput** — ONA can process thousands of inference steps per second.
- **Temporal reasoning** — events happen in sequences, and actions have consequences over time. ONA is the engine responsible for reasoning about before/after, cause-and-effect, and sensorimotor loops.
- **Real-time capability** — designed for environments where inferences must complete on a millisecond budget.

## When to reach for ONA

Use the orchestration table in [reference-orchestration.md](./reference-orchestration.md) as the primary guide. In short:

| Situation | Engine |
|---|---|
| Known chain `A → B → C`, static facts | NAL `\|-` |
| Property-based categorical inference | PLN `\|~` |
| **Event sequences, cause/effect from experience** | **ONA** |
| Real-time sensorimotor loops | **ONA** |

If the question mentions *"before/after"*, *"what happens next"*, or *"learn from experience"*, ONA is the default candidate.

## Invocation surface

ONA is reached through the same `(metta ...)` skill as NAL and PLN. The s-expression form depends on the specific operator being used; see the ONA documentation and the bindings loaded by `lib_omegaclaw.metta` for the exact syntax in your deployment.

## Current operational status

The architecture lists ONA as a first-class engine, but empirically it receives **less validation** than NAL and PLN:

- Temporal inference is exposed but has **minimal operational validation** in the current codebase.
- There is **no native mechanism for belief revision triggered by time** — confidence does not automatically decay for stale claims.
- **Real-time feedback loops** (e.g. NAR operator chains) require careful phase tracking and frequently break due to state management failures.

Treat ONA as experimental in OmegaClaw today: use it, but verify outputs against external ground truth before acting on them. See [reference-failure-modes.md](./reference-failure-modes.md) for the full catalogue of known failure modes.

## See also

- [reference-lib-nal.md](./reference-lib-nal.md) — the symbolic sibling engine.
- [reference-lib-pln.md](./reference-lib-pln.md) — the probabilistic sibling engine.
- [reference-orchestration.md](./reference-orchestration.md) — how the LLM picks between the three engines.
