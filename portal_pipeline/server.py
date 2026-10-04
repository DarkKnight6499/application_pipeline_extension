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
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import answer_sheet
import portal_record
import question_corpus
from portal_profile import hard_fact_errors, load_sponsorship_mode, resolve_for_application, resolve_profile, save_override, save_sponsorship_mode
from audited_import import check_source, inspect_application, posting_url
from preflight import run_preflight

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
MAX_BODY = 2_000_000
RESERVED_OUTPUT_COMPONENTS = {"_reference", "applications", "applications.xlsx"}


class Pipeline:
    def __init__(self, source: Path, data: Path):
        self.source = source.resolve()
        self.reference = self.source / "_Reference"
        if not (self.reference / "Resume_Content_Master.json").is_file():
            raise ValueError("The source must be an existing Resume repository.")
        self.data = data.resolve()
        if self.data.is_relative_to(self.source) or self.source.is_relative_to(self.data):
            raise ValueError("Sandbox output and source workflow directories must not overlap.")
        if any(component.casefold() in RESERVED_OUTPUT_COMPONENTS for component in self.data.parts):
            raise ValueError("Sandbox output must not use reference or application tracker paths.")
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

    def _contained(self, path, boundary):
        resolved = path.resolve()
        if not resolved.is_relative_to(boundary):
            raise ValueError("Sandbox path escapes its allowed directory.")
        return resolved

    def _artifact(self, folder, filename):
        directory = self._contained(folder, self.data)
        target = self._contained(directory / filename, directory)
        if target == directory:
            raise ValueError("Sandbox artifact must be a file inside its directory.")
        return target

    def _session_directory(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
            raise ValueError("Invalid session identifier.")
        folder = self._contained(self.data / session_id, self.data)
        if folder == self.data:
            raise ValueError("Session directory must stay inside the sandbox.")
        return folder

    def folder(self, session_id):
        folder = self._session_directory(session_id)
        if not self._artifact(folder, "session.json").is_file():
            raise ValueError("Session not found.")
        return folder

    def current(self):
        path = self._artifact(self.data, "current.json")
        if not path.exists():
            return None
        return self.read(json.loads(path.read_text(encoding="utf-8"))["id"])

    def read(self, session_id):
        folder = self.folder(session_id)
        session = json.loads(self._artifact(folder, "session.json").read_text(encoding="utf-8"))
        session["content"] = json.loads(self._artifact(folder, "resume_content.json").read_text(encoding="utf-8"))
        keywords = self._artifact(folder, "keywords.json")
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
        folder = self._session_directory(session_id)
        folder.mkdir()
        session = {**context, **evidence, "id": session_id, "mode": "audited_import", "state": "built",
                   "tracker_url": context["url"], "url": portal_url or context["url"],
                   "upload_reviewed": False, "resume_sha256": hashlib.sha256(document).hexdigest(),
                   "checks": {"blocking": [], "advisory": ["Existing application audit passed. Read its report below.",
                       "Review wrapping and widows in Word before enabling attachment. Tracker status stays unchanged."]}}
        self._artifact(folder, "Yazad_Madan.docx").write_bytes(document)
        self.atomic.write(self._artifact(folder, "resume_content.json"), content)
        self.atomic.write(self._artifact(folder, "session.json"), session)
        self.atomic.write(self._artifact(self.data, "current.json"), {"id": session_id})
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
        folder = self._session_directory(session_id)
        folder.mkdir()
        content = json.loads(path.read_text(encoding="utf-8"))
        session = {"id": session_id, "company": body["company"].strip(), "role": body["role"].strip(),
                   "url": url, "template": template, "state": "draft", "upload_reviewed": False,
                   "application_id": None, "checks": None}
        self.atomic.write(self._artifact(folder, "resume_content.json"), content)
        self.atomic.write(self._artifact(folder, "session.json"), session)
        self._artifact(folder, "jd.txt").write_text(body["jd"], encoding="utf-8")
        self.intake.save_jd_docx(body["jd"], session["company"], session["role"], str(self._artifact(folder, "JD.docx")))
        self.atomic.write(self._artifact(folder, "keywords.json"), {"company": session["company"], "role": session["role"],
                                                     "keywords": self.intake.extract_keywords(body["jd"])})
        self.atomic.write(self._artifact(self.data, "current.json"), {"id": session_id})
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
        self.atomic.write(self._artifact(folder, "session.json"), session)
        self.atomic.write(self._artifact(folder, "resume_content.json"), content)
        keywords = json.loads(self._artifact(folder, "keywords.json").read_text(encoding="utf-8"))
        keywords.update(resume_terms=terms, eligibility_requirements=eligibility,
                        requirements_reviewed=body.get("requirements_reviewed") is True)
        self.atomic.write(self._artifact(folder, "keywords.json"), keywords)
        result = subprocess.run(["node", str(self.reference / "build_resume.js"), str(self._artifact(folder, "resume_content.json")),
                                 str(self._artifact(folder, "Yazad_Madan.docx"))], cwd=self._session_directory(session_id), capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise ValueError("The existing builder rejected this content: " + result.stderr[-1600:])
        docx = self._artifact(folder, "Yazad_Madan.docx")
        count, words = self.fit.count_bullets_and_words(str(docx))
        blocking, advisory = self.fit.evaluate_fit(count, words)
        _, matched, missing, rate = self.ats.check_resume_terms(str(docx), str(self._artifact(folder, "keywords.json")))
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
                       resume_sha256=hashlib.sha256(self._artifact(folder, "Yazad_Madan.docx").read_bytes()).hexdigest())
        self.atomic.write(self._artifact(folder, "session.json"), session)
        return self.read(session_id)

    def record_for(self, session_id):
        session = self.read(session_id)
        application_id = session.get("application_id")
        if isinstance(application_id, bool) or not isinstance(application_id, int):
            raise ValueError("Only an audited tracker application has a portal record.")
        record = portal_record.load_record(self.data, application_id, session, self.atomic.write)
        return application_id, record

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
        self.atomic.write(self._artifact(folder, "session.json"), session)
        return self.read(session_id)

    def resume(self, session_id, *, for_upload=False):
        folder = self.folder(session_id)
        session = self.read(session_id)
        file = self._artifact(folder, "Yazad_Madan.docx")
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
        data = self._artifact(folder, "Yazad_Madan.docx").read_bytes()
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
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/profile", path)
                    if match:
                        return self.send(200, resolve_for_application(pipeline.source, pipeline.folder(match[1])))
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/record", path)
                    if match:
                        return self.send(200, {"record": pipeline.record_for(match[1])[1]})
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/sponsorship-mode", path)
                    if match:
                        return self.send(200, {"mode": load_sponsorship_mode(pipeline.folder(match[1]))})
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
                         "/fixture-classifier.js": HERE / "extension/classifier.js", "/fixture-engine.js": HERE / "extension/engine.js", "/fixture-panel.js": HERE / "extension/panel.js"}
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
                    if path == "/api/corpus":
                        logged, skipped = question_corpus.log_question(pipeline.data, body.get("questions"), pipeline.atomic.write)
                        return self.send(200, {"logged": logged, "skipped": skipped})
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/override", path)
                    if match:
                        return self.send(200, save_override(pipeline.folder(match[1]), body.get("key"), body.get("value"), body.get("reason")))
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/answer-sheet", path)
                    if match:
                        session = pipeline.read(match[1])
                        folder = pipeline.folder(match[1])
                        session["resume_path"] = str(folder / "Yazad_Madan.docx")
                        sheet = answer_sheet.build_answer_sheet(session, body.get("fields"), body.get("url", ""), body.get("heading", ""))
                        json_path, html_path, markup = answer_sheet.save_sheet(folder, sheet, pipeline.atomic.write)
                        return self.send(200, {"sheet": sheet, "html": markup, "json_path": str(json_path), "html_path": str(html_path)})
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/record", path)
                    if match:
                        application_id, _ = pipeline.record_for(match[1])
                        if isinstance(body.get("page"), dict):
                            record = portal_record.record_page(pipeline.data, application_id, body["page"], pipeline.atomic.write)
                        elif body.get("event"):
                            event = body["event"] if isinstance(body["event"], dict) else {}
                            record = portal_record.append_event(pipeline.data, application_id, event.get("kind", ""), event.get("detail", ""), pipeline.atomic.write)
                        else:
                            raise ValueError("Send a page or an event to record.")
                        return self.send(200, {"record": record})
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/reported-submitted", path)
                    if match:
                        application_id, _ = pipeline.record_for(match[1])
                        record = portal_record.mark_reported_submitted(pipeline.data, application_id, body.get("employer_reference_id"), pipeline.atomic.write)
                        return self.send(200, {"record": record, "command": portal_record.tracker_command(record, date.today().isoformat())})
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/sponsorship-mode", path)
                    if match:
                        return self.send(200, save_sponsorship_mode(pipeline.folder(match[1]), body.get("mode")))
                    match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/preflight", path)
                    if match:
                        fields = body.get("fields")
                        if fields is not None and (not isinstance(fields, list) or len(fields) > 500 or any(not isinstance(f, dict) for f in fields)):
                            raise ValueError("Fields must be a list of at most 500 objects.")
                        session = pipeline.current()
                        if not session or session.get("id") != match[1]:
                            raise ValueError("Preflight applies to the current session only.")
                        return self.send(200, run_preflight(pipeline.source, {key: value for key, value in session.items() if key != "content"}, fields))
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
