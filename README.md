# OmegaClaw Compatibility Agent

This project is a specialized implementation of the **OmegaClaw** framework, developed as part of my second training at **iCog-Labs**. This agent leverages the OmegaClaw neural-symbolic architecture to autonomously manage technical research tasks, specifically performing automated compatibility checks for software ecosystems.

---

## Project Overview

I have customized this OmegaClaw instance to function as an automated research assistant. By integrating the framework with the **NVIDIA provider** using the **MiniMax M3 model**, this agent is capable of performing deep-dive compatibility analysis for complex software stacks (such as PyTorch ecosystem versioning) with high reasoning precision.

---

## Installation & Setup

Follow these steps to set up the environment:

1. **Clone the Repository:**
```bash
git clone https://github.com/trueagi-io/PeTTa
cd PeTTa
mkdir -p repos
git clone https://github.com/Natnael9/OmegaClaw-Core-iCog-Labs-2N-.git repos/OmegaClaw-Core-iCog-Labs-2N-
git clone https://github.com/patham9/petta_lib_chromadb.git repos/petta_lib_chromadb
cp repos/OmegaClaw-Core-iCog-Labs-2N-/run.metta ./

```


2. **Environment Setup:**
*make sure to install [ SWI-Prolog 10.0.2 or later](https://www.swi-prolog.org/)*
*also install the [hugging fce library](https://huggingface.co/intfloat/e5-large-v2)*
```bash
python3 -m venv ./.venv
source ./.venv/bin/activate
python3 -m pip install -r ./repos/OmegaClaw-Core-iCog-Labs-2N-/requirements.txt

```



---

## Running the Agent

### NVIDIA Provider Configuration

To run this agent using the NVIDIA provider with the MiniMax M3 model, ensure your API keys are exported, then execute:

```bash
OMEGACLAW_AUTH_SECRET=<your-secret> \
provider=NVIDIA \
LLM=minimax-m3 \
sh run.sh run.metta

```
*I recommended NVIDIA Because It allowed me to use many tokens for free*

### Running via Telegram

If you prefer to host your agent via **Telegram** instead of IRC, you can launch it using the following command. The agent will auto-bind to the first user that authenticates via the `auth <secret>` command:

```bash
TG_BOT_TOKEN=<your-token-from-botfather> \
OMEGACLAW_AUTH_SECRET=<your-secret> \
commchannel=telegram \
provider=NVIDIA \
sh run.sh run.metta

```

*(Optional: You can also specify `TG_CHAT_ID` if you wish to bind it to a specific channel immediately.)*

---

## Features & Usage

### Compatibility Checking

I have extended the platform to support automated compatibility verification. By passing a target stack, the agent autonomously researches version constraints across the PyTorch ecosystem (torchvision, torchaudio, etc.) and returns verified results.

*eg. if you want to check the compatability of package B,C,D and E with version x.x.x of A it will give you a precise answer by scraping the web using the check_comptability property I created*
 **IRC Interface:** * **Telegram Interface:**

---

## Documentation & Disclaimer

This project is built upon the OmegaClaw framework, which is experimental, open-source software developed by SingularityNET Foundation.

* **Full Documentation:** Located in `[Docs from main repo](https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/README.md)`.
* **Disclaimer:** By using this software, you acknowledge that OmegaClaw is an autonomous agent that may execute shell commands and modify files. Always run in an isolated environment.

---

*Developed by Natnael during iCog-Labs Training Cycle 2. framework cloned from https://github.com/asi-alliance/OmegaClaw-Core/*