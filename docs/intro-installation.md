# Installation

OmegaClaw supports two setups: the recommended Docker one-liner and a manual MeTTa install.

## Option A — Docker (recommended)

Requirements: Docker.

```bash
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/heads/main/scripts/omegaclaw_setup.sh \
  | bash -s -- singularitynet/omegaclaw:latest
```

The script prompts for:

- an LLM API key (OpenAI by default)
- a unique IRC channel name

and prints a one-time secret used to authenticate the first IRC user. See [tutorial-01-first-run.md](./tutorial-01-first-run.md) for the full first-run walkthrough.

Container management:

| Action | Command |
|---|---|
| Stop | `docker stop omegaclaw` |
| Restart | `docker start omegaclaw` |
| View logs | `docker logs -f omegaclaw` |

Memory persists across restarts because `memory/history.metta` and the ChromaDB store are kept in the container volume.

## Option B — Manual

Requirements: a working MeTTa / Hyperon install, Python 3, and the Python dependencies pulled in by `lib_llm_ext.py`, `src/agentverse.py`, `channels/*.py`, and the ChromaDB bridge.

1. Clone the repository.
2. Export any required API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) depending on the `provider` you choose in `src/loop.metta`.
3. Run:

```bash
metta run.metta
```

Command-line overrides follow `argk` convention (`key=value`), e.g.:

```bash
metta run.metta provider=Anthropic LLM=claude-opus-4-6
```

## Environment variables and API keys

Which keys you need depends on the selected providers:

- **LLM provider** (`provider` in `src/loop.metta`): `OpenAI`, `Anthropic`, or `ASICloud`.
- **Embedding provider** (`embeddingprovider` in `src/memory.metta`): `OpenAI` or `Local`. `Local` uses a Python-side embedding model and needs no key.
- **Channel**: IRC works anonymously against QuakeNet; Mattermost needs `MM_BOT_TOKEN` set in `src/channels.metta` or via `configure`.

All runtime parameters are listed in [reference-configuration.md](./reference-configuration.md).
