"""Local prototype server. The source workflow is read-only; outputs are sandboxed."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import mimetypes
import re
import secrets
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from portal_profile import hard_fact_errors, resolve_profile
from audited_import import check_source, inspect_application, posting_url

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
MAX_BODY = 2_000_000


class Pipeline:
    def __init__(self, source: Path, data: Path):
        self.source = source.resolve()
        self.reference = self.source / "_Reference"
        if not (self.reference / "Resume_Content_Master.json").is_file():
            raise ValueError("The source must be an existing Resume repository.")
        self.data = data.resolve()
        if self.data == self.source or self.data.is_relative_to(self.reference) or self.data.is_relative_to(self.source / "Applications"):
            raise ValueError("Sandbox output must not use the source references or Applications folder.")
        self.data.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(self.reference))
        import atomic_json
        import check_ats
        import check_page_fit
        import jd_intake
        import scan_em_dashes
        self.atomic, self.ats, self.fit, self.intake, self.punctuation = atomic_json, check_ats, check_page_fit, jd_intake, scan_em_dashes
        self.lock = threading.RLock()

    def templates(self):
        return ["Resume_Content_Master.json"] + [p.name for p in sorted((self.reference / "Drafts").glob("*.json"))]

    def folder(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
            raise ValueError("Invalid session identifier.")
        folder = self.data / session_id
        if not (folder / "session.json").is_file():
            raise ValueError("Session not found.")
        return folder

    def current(self):
        path = self.data / "current.json"
        if not path.exists():
            return None
        return self.read(json.loads(path.read_text(encoding="utf-8"))["id"])

    def read(self, session_id):
        folder = self.folder(session_id)
        session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        session["content"] = json.loads((folder / "resume_content.json").read_text(encoding="utf-8"))
        keywords = folder / "keywords.json"
        if keywords.is_file():
            session["requirements"] = json.loads(keywords.read_text(encoding="utf-8"))
        return session

    def import_application(self, body):
        selected = body.get("folder")
        if not isinstance(selected, str) or not selected.strip() or len(selected) > 4000:
            raise ValueError("Provide the exact existing application folder path.")
        portal_url = body.get("portal_url", "")
        if not isinstance(portal_url, str) or len(portal_url) > 4000:
            raise ValueError("The portal posting URL must be a string within the length limit.")
        portal_url = posting_url(portal_url) if portal_url.strip() else None
        context, content, document, evidence = inspect_application(self.source, selected)
        session_id = uuid.uuid4().hex
        folder = self.data / session_id
        folder.mkdir()
        session = {**context, **evidence, "id": session_id, "mode": "audited_import", "state": "built",
                   "tracker_url": context["url"], "url": portal_url or context["url"],
                   "upload_reviewed": False, "resume_sha256": hashlib.sha256(document).hexdigest(),
                   "checks": {"blocking": [], "advisory": ["Existing application audit passed. Read its report below.",
                       "Review wrapping and widows in Word before enabling attachment. Tracker status stays unchanged."]}}
        (folder / "Yazad_Madan.docx").write_bytes(document)
        self.atomic.write(folder / "resume_content.json", content)
        self.atomic.write(folder / "session.json", session)
        self.atomic.write(self.data / "current.json", {"id": session_id})
        return self.read(session_id)

    def create(self, body):
        template = body.get("template", "Resume_Content_Master.json")
        if template not in self.templates():
            raise ValueError("Select a known resume template.")
        for key in ("company", "role", "jd"):
            if not isinstance(body.get(key), str) or not body[key].strip() or len(body[key]) > (100000 if key == "jd" else 300):
                raise ValueError(f"Provide a nonempty {key} within the length limit.")
        url = body.get("url", "")
        if not isinstance(url, str) or len(url) > 4000 or (url and urlsplit(url).scheme not in {"http", "https"}):
            raise ValueError("Posting URL must use HTTP or HTTPS.")
        path = self.reference / template if template == "Resume_Content_Master.json" else self.reference / "Drafts" / template
        session_id = uuid.uuid4().hex
        folder = self.data / session_id
        folder.mkdir()
        content = json.loads(path.read_text(encoding="utf-8"))
        session = {"id": session_id, "company": body["company"].strip(), "role": body["role"].strip(),
                   "url": url, "template": template, "state": "draft", "upload_reviewed": False,
                   "application_id": None, "checks": None}
        self.atomic.write(folder / "resume_content.json", content)
        self.atomic.write(folder / "session.json", session)
        (folder / "jd.txt").write_text(body["jd"], encoding="utf-8")
        self.intake.save_jd_docx(body["jd"], session["company"], session["role"], str(folder / "JD.docx"))
        self.atomic.write(folder / "keywords.json", {"company": session["company"], "role": session["role"],
                                                     "keywords": self.intake.extract_keywords(body["jd"])})
        self.atomic.write(self.data / "current.json", {"id": session_id})
        return self.read(session_id)

    def build(self, session_id, body):
        folder = self.folder(session_id)
        session = self.read(session_id)
        if session.get("mode") == "audited_import":
            raise ValueError("An imported resume must be edited and audited through the current workflow, then imported again.")
        content = body.get("content")
        if not isinstance(content, dict):
            raise ValueError("Provide the reviewed resume content object.")
        master = json.loads((self.reference / "Resume_Content_Master.json").read_text(encoding="utf-8"))
        errors = hard_fact_errors(content, master)
        if errors:
            raise ValueError(" ".join(errors))
        raw = json.dumps(content, ensure_ascii=False)
        if "\u2014" in raw or "--" in raw:
            raise ValueError("Rewrite dash punctuation before building.")
        terms = body.get("resume_terms", [])
        eligibility = body.get("eligibility", [])
        if not isinstance(terms, list) or len(terms) > 30 or any(not isinstance(t, str) or not t.strip() for t in terms):
            raise ValueError("Resume terms must be a list of nonempty strings.")
        if not isinstance(eligibility, list) or len(eligibility) > 50:
            raise ValueError("Eligibility must be a checklist.")
        for item in eligibility:
            if not isinstance(item, dict) or not item.get("requirement") or item.get("meets") not in {"yes", "no", "partial"} or item.get("severity", "required") not in {"required", "preferred"}:
                raise ValueError("Eligibility items require requirement, meets (yes/no/partial), and severity (required/preferred).")
        session.pop("content", None)
        session.pop("requirements", None)
        session.update(state="draft", upload_reviewed=False, checks=None)
        self.atomic.write(folder / "session.json", session)
        self.atomic.write(folder / "resume_content.json", content)
        keywords = json.loads((folder / "keywords.json").read_text(encoding="utf-8"))
        keywords.update(resume_terms=terms, eligibility_requirements=eligibility,
                        requirements_reviewed=body.get("requirements_reviewed") is True)
        self.atomic.write(folder / "keywords.json", keywords)
        result = subprocess.run(["node", str(self.reference / "build_resume.js"), str(folder / "resume_content.json"),
                                 str(folder / "Yazad_Madan.docx")], cwd=folder, capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise ValueError("The existing builder rejected this content: " + result.stderr[-1600:])
        docx = folder / "Yazad_Madan.docx"
        count, words = self.fit.count_bullets_and_words(str(docx))
        blocking, advisory = self.fit.evaluate_fit(count, words)
        _, matched, missing, rate = self.ats.check_resume_terms(str(docx), str(folder / "keywords.json"))
        if keywords["requirements_reviewed"] is not True:
            blocking.append("JD requirements have not been reviewed.")
        if body.get("content_reviewed") is not True:
            blocking.append("Resume claims have not been reviewed against verified experience.")
        if missing:
            blocking.append("Missing reviewed resume terms: " + ", ".join(missing))
        if self.punctuation.find_em_dashes(str(docx)):
            blocking.append("Punctuation check failed.")
        from docx import Document
        properties = Document(docx).core_properties
        if properties.author != "Yazad Madan" or properties.last_modified_by != "Yazad Madan":
            blocking.append("Author metadata check failed.")
        advisory += [f"Eligibility {e['meets']}: {e['requirement']}" for e in eligibility if e["meets"] != "yes"]
        advisory.append("Visual wrapping and widows require review in Word. This prototype does not run the full application audit or write a tracker row.")
        session.update(state="built" if not blocking else "needs_review",
                       content_reviewed=body.get("content_reviewed") is True,
                       checks={"bullets": count, "words": words, "terms_matched": matched,
                               "terms_missing": missing, "terms_rate": rate, "blocking": blocking, "advisory": advisory},
                       resume_sha256=hashlib.sha256(docx.read_bytes()).hexdigest())
        self.atomic.write(folder / "session.json", session)
        return self.read(session_id)

    def approve_upload(self, session_id, body):
        folder = self.folder(session_id)
        session = self.read(session_id)
        if session["state"] != "built" or body.get("visual_reviewed") is not True:
            raise ValueError("Build without blocking issues and review the document in Word before enabling upload.")
        if session.get("mode") == "audited_import":
            check_source(self.source, session)
        session.pop("content", None)
        session.pop("requirements", None)
        session["upload_reviewed"] = True
        self.atomic.write(folder / "session.json", session)
        return self.read(session_id)

    def resume(self, session_id, *, for_upload=False):
        folder = self.folder(session_id)
        session = self.read(session_id)
        file = folder / "Yazad_Madan.docx"
        if not file.is_file():
            raise ValueError("Build a resume first.")
        if for_upload and (not session["upload_reviewed"] or session["state"] != "built"):
            raise ValueError("This resume has not passed the build checks and upload review.")
        if for_upload and session.get("mode") == "audited_import":
            check_source(self.source, session)
        elif for_upload:
            target = urlsplit(session.get("url", ""))
            if target.hostname != "127.0.0.1" or target.path != "/fixture":
                raise ValueError("Sandbox documents attach only to the local fixture. Import an audited application for a real portal.")
        data = file.read_bytes()
        if for_upload and hashlib.sha256(data).hexdigest() != session.get("resume_sha256"):
            raise ValueError("The document changed after review. Rebuild and review it again.")
        return data


def make_server(pipeline, port=8766, token=None):
    token = token or secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, value, content_type="application/json", extra=None):
            data = json.dumps(value).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, val in (extra or {}).items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            address = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != address:
                self.send(403, {"error": "Use the exact loopback address shown at startup."})
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + address and not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
                self.send(403, {"error": "Request origin is not allowed."})
                return False
            if urlsplit(self.path).path.startswith("/api/"):
                supplied = self.headers.get("X-Portal-Token", "")
                if not secrets.compare_digest(supplied, token):
                    self.send(401, {"error": "Pair the extension with this server's token."})
                    return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            path = urlsplit(self.path).path
            try:
                with pipeline.lock:
                    if path == "/api/profile":
                        return self.send(200, resolve_profile(pipeline.source))
                    if path == "/api/config":
                        return self.send(200, {"templates": pipeline.templates(), "current": pipeline.current()})
                    if path == "/api/current":
                        return self.send(200, pipeline.current())
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/(download|attachment)", path)
                    if match:
                        data = pipeline.resume(match[1], for_upload=match[2] == "attachment")
                        if match[2] == "attachment":
                            return self.send(200, {"name": "Yazad_Madan.docx", "base64": base64.b64encode(data).decode(),
                                                   "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                                   "sha256": hashlib.sha256(data).hexdigest(), "session_id": match[1]})
                        return self.send(200, data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                         {"Content-Disposition": 'attachment; filename="Yazad_Madan.docx"'})
                files = {"/": HERE / "web/index.html", "/app.js": HERE / "web/app.js", "/style.css": HERE / "web/style.css",
                         "/fixture": HERE / "fixtures/workday.html", "/fixture.js": HERE / "fixtures/workday.js",
                         "/fixture-adapter.js": HERE / "extension/adapters/aria-listbox.js",
                         "/fixture-engine.js": HERE / "extension/engine.js", "/fixture-panel.js": HERE / "extension/panel.js"}
                file = files.get(path)
                if not file:
                    return self.send(404, {"error": "Not found."})
                data = file.read_bytes()
                if path in {"/", "/fixture"}:
                    data = data.replace(b"PAIRING_TOKEN", token.encode())
                mime = mimetypes.guess_type(file)[0] or "application/octet-stream"
                return self.send(200, data, mime + "; charset=utf-8")
            except (ValueError, FileNotFoundError) as error:
                self.send(400, {"error": str(error)})

        def do_POST(self):
            if not self.allowed():
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    return self.send(413, {"error": "Request exceeds the size limit or has no body."})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Request must be a JSON object.")
                path = urlsplit(self.path).path
                with pipeline.lock:
                    if path == "/api/sessions":
                        return self.send(201, pipeline.create(body))
                    if path == "/api/import":
                        return self.send(201, pipeline.import_application(body))
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/(build|approve-upload)", path)
                    if match:
                        method = pipeline.build if match[2] == "build" else pipeline.approve_upload
                        return self.send(200, method(match[1], body))
                self.send(404, {"error": "Not found."})
            except (ValueError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired) as error:
                self.send(400, {"error": str(error)})
            except Exception:
                self.send(500, {"error": "Operation failed. No application was submitted or tracker changed."})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = token
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE.parent, help="Existing resume repository, read-only")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    pipeline = Pipeline(args.source, HERE / "data")
    server = make_server(pipeline, args.port)
    print(f"Portal prototype: http://127.0.0.1:{server.server_port}", flush=True)
    print("Open the dashboard to copy the extension pairing token. Ctrl+C stops the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
