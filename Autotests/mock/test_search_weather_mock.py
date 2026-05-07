"""
Mock variant of test_search_weather.

Same scoping note as the other search mocks: the LLM dispatch is
mocked, the search skill is not. To keep the mock variant deterministic
the response is delivered directly via (send ...). The reply is built
around the live open-meteo reference temperature so the cross-check
assertion (±10°C) still has real meaning — if open-meteo returns
something different at run time, the mocked send tracks it.

Run:
    pytest test_search_weather_mock.py -s
"""
import json
import re
import urllib.request

import mock.rpc as rpc
from mock.llm import llm_mock_controller

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_match,
)

VALENCIA_LAT = 39.47
VALENCIA_LON = -0.38
OPEN_METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={VALENCIA_LAT}&longitude={VALENCIA_LON}&current_weather=true"
)


def fetch_reference_weather():
    req = urllib.request.Request(OPEN_METEO_URL, headers={"User-Agent": "smoke/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    return data.get("current_weather", {})


def test_search_weather_mock():
    with Checker("search weather valencia (mock)") as c, \
            llm_mock_controller(("0.0.0.0", rpc.PORT_DEFAULT)) as llm:
        print(f"\n=== OmegaClaw: Valencia weather mock (run-id {c.run_id}) ===",
              flush=True)

        c.step("fetch reference weather from open-meteo")
        ref = fetch_reference_weather()
        if ref.get("temperature") is None:
            c.fail("open-meteo", f"no temperature in response: {ref}")
        ref_temp = float(ref["temperature"])
        c.ok("open-meteo", f"reference temp={ref_temp}°C")

        c.step("send prompt via IRC with mocked send response")
        prompt = make_prompt(
            c.run_id,
            "What's the weather in Valencia Spain today? "
            "Search the web and tell me temperature in Celsius.",
        )
        # Construct the mocked reply around the live reference value so
        # the ±10°C cross-check exercises the same numeric tolerance as
        # the live test. Round to one decimal for naturalness.
        mocked_reply = (
            f"Current weather in Valencia, Spain: about {ref_temp:.1f}°C."
        )
        llm.set_answer(prompt, f'(send "{mocked_reply}")')
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify (send ...) carries a plausible Celsius temperature")

        def has_plausible_temp(s):
            return any(-20 <= float(n) <= 50
                       for n in re.findall(r"-?\d+(?:\.\d+)?", s))

        send_arg = wait_for_skill_match(
            c.run_id, "send", has_plausible_temp, timeout=30,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            last = all_sends[-1] if all_sends else "<none>"
            c.fail("send with temp", f"no send with plausible temp. Last: {last!r}")
        c.ok("send invoked", f"{len(send_arg)} chars")

        c.step("cross-check temperature with open-meteo (±10°C)")
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", send_arg)
                if -20 <= float(n) <= 50]
        in_range = [n for n in nums if abs(n - ref_temp) <= 10]
        if not in_range:
            c.fail("cross-check",
                   f"agent temps {nums} vs open-meteo {ref_temp}°C")
        c.ok("cross-check", f"{in_range} within ±10°C of {ref_temp}°C")

        c.done()
