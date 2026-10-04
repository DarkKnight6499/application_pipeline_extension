"""Replay helpers: load the manifest, run recorded synthetic pages through the adapter interface, compare counts."""
import json
import re

from browser_test_support import HERE, SyntheticBrowserTest

# Replay configuration
REPLAY_DIR = HERE / "fixtures" / "replay"
MANIFEST = REPLAY_DIR / "manifest.json"
PAGES = REPLAY_DIR
GUARD_PREFIX = "guard-"
INTERFACE_PROBE = """() => {
  const adapter = PortalAdapters.forLocation(location.href);
  const gate = adapter.humanGate(document);
  return {adapter: adapter.id, gate: gate && gate.kind, final: adapter.detectFinalReview().final, next: adapter.nextStep().kind};
}"""


def load_cases():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]


def drop_label(html, text):
    return re.sub(r"(<label[^>]*>)\s*" + re.escape(text), r"\1", html, count=1)


def duplicate_first_input(html):
    return re.sub(r"(<input\b[^>]*>)", r"\1\1", html, count=1)


def compare(case, observed):
    """Return one message per expected key whose observed value differs."""
    expected = case["expect"]
    pairs = {"fields": "fields", "required": "required", "keys": "keys", "human_gate": "human_gate",
             "final_review": "final_review", "next_kind": "next_kind"}
    problems = [f"{key}: expected {expected[key]!r}, got {observed[name]!r}" for key, name in pairs.items() if expected[key] != observed[name]]
    for item in observed["fill"]:
        if item["status"] != item["want_status"] or item["after"] != item["want_after"]:
            problems.append(f"fill {item['key']}: {item['status']} {item['after']!r}")
    for item in observed["untouched"]:
        if item["changed"]:
            problems.append(f"untouched {item['selector']} changed")
    return problems


class ReplayBrowserTest(SyntheticBrowserTest):
    def replay(self, case, html):
        self.open_markup(html, case["url"])
        fields = [field for field in self.scan() if not field["structure"]["dom_id"].startswith(GUARD_PREFIX)]
        probe = self.page.evaluate(INTERFACE_PROBE)
        fills = []
        for step in case.get("fill", []):
            match = next((field for field in fields if field["key"] == step["key"]), None)
            result = self.fill([{"id": match["id"], "value": step["value"]}])[0] if match else {"status": "no_such_field"}
            after = self.page.locator(step["selector"]).first.input_value()
            fills.append({"key": step["key"], "status": result["status"], "after": after,
                          "want_status": step["status"], "want_after": step["after"]})
        untouched = [{"selector": item["selector"],
                      "changed": self.page.locator(item["selector"]).first.input_value() != item["value"]} for item in case.get("untouched", [])]
        return {"adapter": probe["adapter"], "fields": len(fields), "required": sum(1 for field in fields if field["required"]),
                "keys": sorted({field["key"] for field in fields if field["key"]}), "human_gate": probe["gate"],
                "final_review": probe["final"], "next_kind": probe["next"], "fill": fills, "untouched": untouched,
                "submit_counts": self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents, 0]")}
