"""Explicit source configuration keeps test results attributable to one checkout."""
import os
import shutil
from pathlib import Path

# Integration test configuration
SOURCE_ENVIRONMENT = "PORTAL_SOURCE"
INTEGRATION_SKIP_REASON = "SKIPPED-BY-ENVIRONMENT: set PORTAL_SOURCE for external workflow integration."


def workflow_source():
    configured = os.environ.get(SOURCE_ENVIRONMENT)
    if not configured:
        return None
    source = Path(configured).resolve()
    if not (source / "_Reference/build_resume.js").is_file() or not (source / "node_modules/docx").is_dir():
        raise RuntimeError("Set PORTAL_SOURCE to the existing Resume checkout with its Node builder dependencies installed.")
    return source


def audited_fixture(root, built_folder, workflow):
    """Create an application and tracker without writing the production checkout."""
    from openpyxl import Workbook
    source = root / "synthetic-source"
    reference = source / "_Reference"
    reference.mkdir(parents=True)
    shutil.copyfile(workflow / "_Reference/Resume_Content_Master.json", reference / "Resume_Content_Master.json")
    # Execute the original audit in place with only its tracker path redirected.
    audit_file = str(workflow / "_Reference/audit_application.py")
    tracker = str(source / "Applications.xlsx")
    (reference / "audit_application.py").write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('existing_audit', {audit_file!r})\n"
        "audit = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(audit)\n"
        f"audit.XLSX_PATH = {tracker!r}\naudit.main()\n", encoding="utf-8")
    folder = source / "Applications/2026-10-03_SyntheticEmployer_TreasuryAnalyst"
    inputs = folder / "_inputs"
    inputs.mkdir(parents=True)
    (folder / ".application_id").write_text("900001", encoding="utf-8")
    shutil.copyfile(built_folder / "Yazad_Madan.docx", folder / "Yazad_Madan.docx")
    shutil.copyfile(built_folder / "JD.docx", folder / "JD_SyntheticEmployer_TreasuryAnalyst.docx")
    shutil.copyfile(built_folder / "resume_content.json", inputs / "resume_content.json")
    shutil.copyfile(built_folder / "keywords.json", inputs / "Keywords_SyntheticEmployer_TreasuryAnalyst.json")
    workbook = Workbook()
    workbook.properties.creator = "Yazad Madan"
    workbook.properties.lastModifiedBy = "Yazad Madan"
    workbook.active.append(["Application ID", "Company", "Role Title", "Link", "Status"])
    workbook.active.append([900001, "Synthetic Employer", "Treasury Analyst", "https://example.myworkdayjobs.com/role/900001", "To Apply"])
    workbook.save(source / "Applications.xlsx")
    workbook.close()
    return source, folder
