"""edge_launch with injected fakes; no real Edge is started."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import edge_launch as e

# Config
PROFILE = Path(r"D:\Code\application_pipeline\browser_profile")
EXE = r'"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"'
GOOD = f'{EXE} --remote-debugging-port=9223 --user-data-dir="{PROFILE}" --no-first-run'
OTHER = EXE + r' --remote-debugging-port=9223 --user-data-dir="C:\Users\someone\AppData\Local\Microsoft\Edge\User Data"'
NO_PROFILE = '"msedge.exe" --remote-debugging-port=9223'


class Fakes:
    def __init__(self, answering=False, command_line=GOOD, answer_after=1):
        self.answering, self.command_line, self.answer_after = answering, command_line, answer_after
        self.started, self.probes = [], 0

    def probe(self):
        self.probes += 1
        if self.started and self.probes > self.answer_after:
            self.answering = True
        return self.answering

    def start(self, command):
        self.started.append(command)

    def owner(self):
        return self.command_line


def run(fakes, **extra):
    return e.ensure_edge(probe=fakes.probe, start=fakes.start, owner_command_line=fakes.owner, sleep=lambda _s: None, **extra)


def test_already_answering_with_dedicated_profile_starts_nothing():
    fakes = Fakes(answering=True)
    assert run(fakes)["started"] is False
    assert fakes.started == []


def test_not_answering_starts_edge_with_port_and_profile_and_waits():
    fakes = Fakes()
    result = run(fakes)
    assert result["started"] is True and len(fakes.started) == 1
    command = fakes.started[0]
    assert "--remote-debugging-port=9223" in command and f"--user-data-dir={PROFILE}" in command


def test_second_call_starts_no_new_process():
    fakes = Fakes()
    run(fakes)
    assert run(fakes)["started"] is False
    assert len(fakes.started) == 1


@pytest.mark.parametrize("command_line", [OTHER, NO_PROFILE, None])
def test_port_owner_with_other_profile_is_refused(command_line):
    with pytest.raises(e.EdgeRefused):
        run(Fakes(answering=True, command_line=command_line))


def test_started_edge_with_foreign_owner_is_refused():
    with pytest.raises(e.EdgeRefused):
        run(Fakes(command_line=OTHER))


def test_timeout_when_edge_never_answers():
    fakes = Fakes(answer_after=10 ** 9)
    ticks = iter(range(0, 10 ** 6))
    with pytest.raises(e.EdgeNotReady):
        e.ensure_edge(probe=fakes.probe, start=fakes.start, owner_command_line=fakes.owner, sleep=lambda _s: None, clock=lambda: next(ticks) * 10)


def test_profile_match_ignores_case_quotes_and_trailing_slash():
    assert e.uses_profile('x --user-data-dir="' + str(PROFILE).lower() + '\\"', PROFILE)
    assert not e.uses_profile(f"x --user-data-dir={PROFILE}_other", PROFILE)
