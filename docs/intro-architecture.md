# Architecture

OmegaClaw is a hybrid system. A thin MeTTa core drives two formal reasoning engines (NAL and PLN) and a handful of Python bridges for LLM calls, embeddings, and network I/O.

## Layered view

```
┌─────────────────────────────────────────────────┐
│  LLM Layer                                      │
│  - Natural language understanding               │
│  - Premise formulation (atomization)            │
│  - Inference orchestration                      │
│  - Contextual steering                          │
└────────────────────┬────────────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
┌──────────┐                 ┌──────────┐
│ NAL   |- │                 │ PLN   |~ │
│ Engine   │                 │ Engine   │
└────┬─────┘                 └────┬─────┘
     │                            │
     └─────────────┬──────────────┘
                   │
       ┌────────────┴────────────┐
       ▼                         ▼
┌────────────────┐     ┌──────────────────┐
│ Memory 3-tier  │     │ Shell / Files /  │
│ - pin  (ST)    │     │ Channels / Web   │
│ - remember LT  │     │                  │
│ - AtomSpace    │     │                  │
└────────────────┘     └──────────────────┘
```

The **LLM layer** is opaque and creative. The **engine layer** is deterministic and auditable. The separation is the point — confidence math cannot be inflated by rhetoric.

## Module map

```
run.metta                 entry point: (omegaclaw)
lib_omegaclaw.metta       loads all submodules
├── src/loop.metta        agentic loop, turn structure
├── src/memory.metta      long-term memory + history
├── src/skills.metta      callable skill surface
├── src/channels.metta    receive/send/search dispatch
├── src/utils.metta       configure, string ops, time
├── src/helper.py         parenthesis balancing, normalization
├── src/agentverse.py     remote-agent bridge
├── src/skills.pl         Prolog helpers (shell, first_char)
├── lib_nal.metta         NAL truth functions
├── lib_pln.metta         PLN rules
└── lib_llm_ext.py        Claude / GPT / MiniMax / local embeddings

channels/irc.py           IRC adapter
channels/mattermost.py    Mattermost adapter
channels/websearch.py     web search

memory/prompt.txt         system prompt (agent identity + values)
memory/history.metta      episodic trace (written at runtime)
```

## The agentic turn

Each iteration of `(omegaclaw $k)` in `src/loop.metta` performs:

```
┌─────────────────────────────────────────────────────────┐
│ 1. receive()        pull latest message from channel    │
│ 2. getContext()     PROMPT + SKILLS +                   │
│                     LAST_SKILL_USE_RESULTS +            │
│                     HISTORY + TIME                      │
│ 3. LLM call         Anthropic / OpenAI / ASICloud       │
│ 4. sread / balance  parse response into skill s-exprs   │
│ 5. eval each skill  (remember ...), (metta ...), ...    │
│ 6. addToHistory     append human msg + response +       │
│                     any errors                          │
│ 7. sleep            sleepInterval seconds               │
│ 8. recurse          (omegaclaw (+ 1 $k))                │
└─────────────────────────────────────────────────────────┘
```

If no new message arrives and the `loops` counter hits zero, the agent idles until `nextWakeAt`, then runs one wake loop for background work.

## The reasoning sub-cycle (neural ↔ symbolic)

When a skill-tuple contains a `(metta (|- ...))` or `(metta (|~ ...))` call, a second, shorter rhythm kicks in **inside** step 5 above — a strict call-and-wait between the LLM and the formal engine:

```
1. NEURAL PHASE
   LLM emits (metta "(|- ...)")

2. INTERCEPTION
   Framework suspends LLM generation and
   hands the s-expression to MeTTa.

3. SYMBOLIC PHASE
   MeTTa / Hyperon runs the inference
   independently of the LLM.

4. RESULT CAPTURE
   Engine returns a result atom,
   e.g. (--> robin animal) (stv 0.72 0.32)

5. INJECTION & RESUMPTION
   Result is written into &lastresults and
   appears in the next prompt as
   LAST_SKILL_USE_RESULTS. LLM resumes.
```

This rhythm is what makes conclusions auditable: the LLM cannot alter the truth-value math that produced them.

## Division of labor

| Controlled by the LLM (opaque) | Controlled by the engine (transparent) |
|---|---|
| Which premises to include | How truth values propagate |
| Initial `(stv f c)` assignments | Confidence decay through chains |
| Which inference rule to invoke | The math of the rule |
| When to stop reasoning | Whether the conclusion follows |

See [reference-orchestration.md](./reference-orchestration.md) for the LLM's side of the policy.

## Data flow — a grounded memory write

```
user message
   │
   ▼
(receive) ─► channel adapter ─► loop input
                                   │
                                   ▼
                            LLM atomizes:
                            (remember "...")
                                   │
                                   ▼
              src/memory.metta ─► embed() ─► lib_llm_ext ─► vector
                                   │
                                   ▼
                  lib_chromadb.remember(str, vec, timestamp)
```

For a **grounded** write with provenance, the pattern is the same, but the LLM first queries memory, then fetches from a verified source before calling `remember`. See [tutorial-08-grounded-reasoning.md](./tutorial-08-grounded-reasoning.md).

## Three-tier memory interaction

A reasoning-heavy turn typically uses all three memory tiers:

```
1. query long-term memory for relevant past findings
        │
        ▼
2. atomize relevant knowledge into AtomSpace
        │
        ▼
3. reason over atoms via (metta (|- ...)) or (|~ ...)
        │
        ▼
4. remember novel conclusions with provenance
        │
        ▼
5. pin reasoning state for the next cycle
```

## Configuration

Runtime parameters are declared as `(empty)` at module top and filled by `configure` calls during `initLoop`, `initMemory`, and `initChannels`. Command-line overrides are accepted via the `argk` helper in `src/utils.metta`. Full list in [reference-configuration.md](./reference-configuration.md).

## Further reading

- [intro-hybrid-reasoning.md](./intro-hybrid-reasoning.md) — the architecture's central thesis.
- [reference-internals-loop.md](./reference-internals-loop.md) — turn structure in detail.
- [reference-internals-memory-store.md](./reference-internals-memory-store.md) — the three memory tiers.
- [reference-internals-skill-dispatch.md](./reference-internals-skill-dispatch.md) — how skill calls resolve.
- [reference-internals-extension-points.md](./reference-internals-extension-points.md) — where to plug in new behavior.
