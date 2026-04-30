"""
Test: agent invokes the (metta ...) skill on explicit request.

The metta skill executes a MeTTa s-expression inside the agent. We ask the
agent to evaluate a tiny self-chosen MeTTa expression and report the result;
we accept any (metta ...) call and a follow-up (send ...) that references
the result. Agent can pick whichever expression it wants — the goal is to
exercise the skill, not to grade MeTTa semantics.

Run:
    pytest test_skill_metta.py -s
"""
from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call,
)


def test_skill_metta():
    with Checker("metta skill invocation") as c:
        print(f"\n=== OmegaClaw: metta skill (run-id {c.run_id}) ===", flush=True)

        c.step("send prompt asking agent to use metta skill")
        prompt = make_prompt(
            c.run_id,
            "Please demonstrate your `metta` skill: pick any short MeTTa "
            "expression you like, evaluate it via the metta skill, and tell "
            "me what it returned. One short reply is enough.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked (metta ...)")
        metta_arg = wait_for_skill_call(c.run_id, "metta", timeout=240)
        if metta_arg is None:
            c.fail("metta invoked", "no (metta ...) call within 240s")
        c.ok("metta invoked", f"arg={metta_arg[:80]!r}")

        c.step("verify agent then sent a reply mentioning the result")
        send_arg = wait_for_skill_call(c.run_id, "send", timeout=120)
        if send_arg is None:
            c.fail("send invoked", "agent did not send a reply after metta")
        c.ok("send invoked", f"reply={send_arg[:80]!r}")

        c.done()
