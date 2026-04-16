# Overview

OmegaClaw is a **hybrid agentic AI framework** implemented in MeTTa on OpenCog Hyperon. A large language model (LLM) works together with formal logic engines — **NAL**, **PLN**, and **ONA** — to reason about the world, track uncertainty, combine evidence, and produce conclusions that are mathematically grounded rather than just plausible-sounding.

The core agent loop is approximately **200 lines of MeTTa**.

## What makes OmegaClaw different

Most AI assistants generate answers that sound right. OmegaClaw-hosted agents generate answers that come with a **mathematical receipt** showing exactly how confident each conclusion is and what evidence supports it.

When the agent says it is 72% confident, that number comes from formal inference — not a feeling.

See [intro-hybrid-reasoning.md](./intro-hybrid-reasoning.md) for the thesis in depth.

## What OmegaClaw does

- Runs a token-efficient agentic loop that receives messages, selects skills, and acts.
- Delegates reasoning to one of three formal engines, orchestrated by the LLM:
  - **NAL** — Non-Axiomatic Logic, symbolic inference under uncertainty.
  - **PLN** — Probabilistic Logic Networks, probabilistic higher-order reasoning.
  - **ONA** — OpenNARS for Applications, real-time and temporal reasoning.
- Maintains a **three-tier memory** architecture:
  1. **Working memory** (`pin`) — volatile, single-slot scratchpad.
  2. **Long-term embedding memory** (`remember` / `query`) — semantic recall across sessions.
  3. **AtomSpace** — atomized, truth-valued knowledge usable by the engines.
- Exposes an extensible **skill system** covering memory, shell and file I/O, communication channels, web search, remote agents, and formal reasoning.

## Design goals

- **Transparency by design, not by post-hoc explanation.** Every conclusion can be traced to its premises, rule, and truth-value math.
- **Simplicity.** A small core that is readable end-to-end.
- **Extensibility.** New skills, channels, tools, and engines are short additions — see [reference-internals-extension-points.md](./reference-internals-extension-points.md).
- **Flexibility in memory representation.** Memory items coexist with other Hyperon components in the same AtomSpace; no single representation is hardcoded.

## When to use OmegaClaw

Use OmegaClaw when you want:

- a small, auditable agent that can explain **why** it reached a conclusion;
- reasoning with explicit uncertainty (`stv frequency confidence`) rather than opaque probabilities;
- a platform for experimenting with NAL / PLN / ONA inside an agent loop;
- a chat-facing agent over IRC, Mattermost, or a channel you add yourself.

## Honest limits

The hybrid design moves the failure mode — it does not eliminate it. Known issues, quantified on the reference deployment:

- LLM premise formulation errors (up to ~16.6% on asymmetric relations).
- LLM confidence overestimation (~15 percentage points on self-assigned truth values).
- Confidence decays ~10% per inference hop; by the third hop, `c` typically drops below 0.5.

The mitigations (external grounding, revision, action thresholds, the defense stack) are documented and non-optional for production use. See [reference-failure-modes.md](./reference-failure-modes.md) and [tutorial-09-reliable-reasoning.md](./tutorial-09-reliable-reasoning.md).

## Where to go next

- [intro-hybrid-reasoning.md](./intro-hybrid-reasoning.md) — the LLM + formal logic thesis.
- [intro-concepts.md](./intro-concepts.md) — vocabulary used throughout the docs.
- [intro-architecture.md](./intro-architecture.md) — how the pieces connect at runtime.
- [intro-installation.md](./intro-installation.md) — get a running instance.
- [tutorial-01-first-run.md](./tutorial-01-first-run.md) — hands-on first session.
