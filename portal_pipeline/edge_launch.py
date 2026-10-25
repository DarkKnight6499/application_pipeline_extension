"""Start the dedicated debuggable Edge on port 9223 if nothing answers, and refuse a port owner that is not our profile."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Config
HOST = "127.0.0.1"
PORT = 9223
PROFILE_DIR = Path(r"D:\Code\application_pipeline\browser_profile")
EDGE_PATHS = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
START_TIMEOUT_SECONDS = 30
POLL_SECONDS = 0.5
PROBE_TIMEOUT_SECONDS = 2
PROFILE_FLAG = "--user-data-dir="
PROFILE_ARG = re.compile(r'--user-data-dir=(?:"([^"]*)"|(\S+))')
OWNER_SCRIPT = ("$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;"
                " if ($c) {{ (Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\").CommandLine }}")


class EdgeRefused(RuntimeError):
    """The port is owned by something other than Edge on the dedicated profile."""


class EdgeNotReady(RuntimeError):
    """Edge was started but never answered on the debug port."""


def probe(port=PORT):
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/json/version", timeout=PROBE_TIMEOUT_SECONDS) as response:
            return "Browser" in json.load(response)
    except Exception:  # noqa: BLE001 - any failure means nothing usable answers
        return False


def port_owner_command_line(port=PORT):
    """Command line of the process listening on the port, via CIM; None when unknown."""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", OWNER_SCRIPT.format(port=port)], capture_output=True, text=True, timeout=20)
    return result.stdout.strip() or None


def normalize(path):
    return os.path.normcase(str(path).strip().strip('"').rstrip("\\/"))


def uses_profile(command_line, profile=PROFILE_DIR):
    """True when the command line names exactly this user-data-dir."""
    return any(normalize(quoted or bare) == normalize(profile) for quoted, bare in PROFILE_ARG.findall(str(command_line or "")))


def edge_command(profile=PROFILE_DIR, port=PORT):
    exe = next((path for path in EDGE_PATHS if Path(path).is_file()), "msedge")
    return [exe, f"--remote-debugging-port={port}", f"{PROFILE_FLAG}{profile}", "--no-first-run"]


def start_edge(command):
    subprocess.Popen(command, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def verify_owner(owner_command_line, port, profile):
    command_line = owner_command_line()
    if not uses_profile(command_line, profile) or f"--remote-debugging-port={port}" not in str(command_line):
        raise EdgeRefused(f"Port {port} is owned by a browser that does not use {profile}. Close it or free the port.")


def ensure_edge(probe=probe, start=start_edge, owner_command_line=port_owner_command_line, sleep=time.sleep, clock=time.monotonic,
                port=PORT, profile=PROFILE_DIR):
    """Make sure the dedicated Edge answers on the port; returns {"started": bool, "port": port}."""
    if probe():
        verify_owner(owner_command_line, port, profile)
        return {"started": False, "port": port}
    start(edge_command(profile, port))
    deadline = clock() + START_TIMEOUT_SECONDS
    while not probe():
        if clock() >= deadline:
            raise EdgeNotReady(f"Edge did not answer on port {port} within {START_TIMEOUT_SECONDS} seconds.")
        sleep(POLL_SECONDS)
    verify_owner(owner_command_line, port, profile)
    return {"started": True, "port": port}


def main():
    try:
        print(ensure_edge())
        return 0
    except (EdgeRefused, EdgeNotReady) as error:
        print(error)
        return 3


if __name__ == "__main__":
    sys.exit(main())
