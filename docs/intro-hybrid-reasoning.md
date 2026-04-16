# Hybrid Reasoning — The Core Thesis

OmegaClaw is a **hybrid system**: a large language model (LLM) works together with formal logic engines to reason about the world, track uncertainty, combine evidence, and reach conclusions that are mathematically grounded rather than just plausible-sounding.

> Most AI assistants generate answers that sound right. OmegaClaw-hosted agents generate answers that come with a **mathematical receipt** showing exactly how confident each conclusion is and what evidence supports it.

This page explains why the hybrid architecture exists and what each layer contributes.

---

## Two kinds of reasoning, one pipeline

| Aspect | LLM (neural) | Formal engine (symbolic) |
|---|---|---|
| Natural language understanding | ✅ | ❌ |
| Premise formulation from text | ✅ | ❌ |
| Inference orchestration (which rule when) | ✅ | ❌ |
| Truth-value propagation | ❌ | ✅ |
| Confidence decay through chains | ❌ | ✅ |
| Formal contradiction detection | ❌ | ✅ |
| Auditable conclusion path | ❌ | ✅ |

The LLM turns ambiguous natural language into structured atoms with explicit truth values. The formal engine takes those atoms and applies rules whose truth-value arithmetic is deterministic and auditable.

When the agent outputs a conclusion, you can trace it back through every step: which premises fed into which rule, what truth value each premise carried, and what the math produced.

---

## The three reasoning engines

OmegaClaw ships three complementary engines, all reachable through the `(metta ...)` skill:

- **NAL** — *Non-Axiomatic Logic*. Symbolic inference under uncertainty, with evidence-based `(stv frequency confidence)` truth values. See [reference-lib-nal.md](./reference-lib-nal.md).
- **PLN** — *Probabilistic Logic Networks*. Higher-order probabilistic reasoning over inheritance and implication relations. See [reference-lib-pln.md](./reference-lib-pln.md).
- **ONA** — *OpenNARS for Applications*. Real-time, high-throughput NARS implementation with temporal reasoning. See [reference-lib-ona.md](./reference-lib-ona.md).

Which engine to use is not a fixed mapping — the LLM orchestrates by pattern. See [reference-orchestration.md](./reference-orchestration.md).

---

## The orchestration cycle (call-and-wait)

Each reasoning hop is a synchronous five-step dance:

```
1. NEURAL PHASE
   LLM synthesizes context, emits a formal command
   (e.g. (metta "(|- ...)"))

2. INTERCEPTION
   The agent framework intercepts the command;
   LLM generation is suspended.

3. SYMBOLIC PHASE
   Framework passes the s-expression to the MeTTa /
   Hyperon interpreter. The engine executes logic
   independently of the LLM.

4. RESULT CAPTURE
   Engine returns deterministic result atoms
   (e.g. (robin --> animal) (stv 0.72 0.32)).

5. INJECTION & RESUMPTION
   Results are injected into the next prompt context
   as immutable data. The LLM resumes, reads the data,
   and decides the next move.
```

This structure matters because step 3 is **opaque to the LLM in a useful way** — the LLM cannot tamper with the truth-value math. Confidence cannot be inflated by rhetoric.

---

## Three-tier memory, in service of reasoning

Hybrid reasoning needs a matching memory layout:

1. **Working memory (`pin`)** — a single-slot scratchpad holding the agent's current task state. Overwritten each cycle. Volatile.
2. **Long-term embedding memory (`remember` / `query`)** — persistent, semantic recall across thousands of cycles.
3. **AtomSpace** — atomized knowledge in formal `(stv ...)` form, used by NAL / PLN / ONA. The knowledge graph the engines reason over.

Atomization (converting natural language to AtomSpace atoms) is a first-class concept — raw text cannot participate in inference. See [reference-internals-memory-store.md](./reference-internals-memory-store.md).

---

## Honest limits

The hybrid design does not magically fix hallucinations. It moves the failure mode:

- If the **LLM formulates bad premises**, the engine amplifies them with mathematical authority. Empirically, asymmetric-relationship formulation errors reach ~16.6%, and confidence self-assignments are overconfident by roughly 15 percentage points.
- Confidence **decays about 10% per inference hop**; by the third hop, confidence typically drops below 0.5.
- **Garbage In, Garbage Out** applies with a twist: the formal engine does not merely pass through garbage, it **amplifies** it by lending mathematical authority to conclusions derived from flawed premises.

These are not surprises — they are measured properties of the current system. The mitigations (external grounding, revision, action thresholds, the defense stack) live in:

- [reference-failure-modes.md](./reference-failure-modes.md) — the full catalogue.
- [tutorial-08-grounded-reasoning.md](./tutorial-08-grounded-reasoning.md) — external grounding in practice.
- [tutorial-09-reliable-reasoning.md](./tutorial-09-reliable-reasoning.md) — strategic advice.

---

## See also

- [intro-concepts.md](./intro-concepts.md) — the vocabulary in detail.
- [intro-architecture.md](./intro-architecture.md) — how the three engines plug into the agent loop.
- [reference-orchestration.md](./reference-orchestration.md) — engine selection, stopping criteria, action thresholds.
