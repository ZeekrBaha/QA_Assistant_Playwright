import difflib
import json
import os
import shlex
import subprocess
from pathlib import Path

from backend.config import settings

ALLOWED_TEST_COMMANDS = {
    "npm test",
    "npm run test",
    "pytest",
    ".venv/bin/python -m pytest",
    "python -m pytest",
    "python3 -m pytest",
    "npx playwright test",
}


def resolve_repo_path(repo_path: str) -> Path:
    candidate = Path(repo_path).expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError("Repository path does not exist or is not a directory.")

    allowed_roots = [Path(root).expanduser().resolve() for root in settings.allowed_repo_roots]
    if not any(candidate == root or root in candidate.parents for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise ValueError(f"Repository path is outside allowed roots: {roots}")
    return candidate


def scan_repo(repo_path: str) -> dict:
    root = resolve_repo_path(repo_path)
    files = _list_interesting_files(root)
    package_json = _load_json(root / "package.json")
    package_json_files = [root / "package.json", root / "frontend" / "package.json"]
    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"

    frameworks = []
    test_frameworks = []
    package_deps = {}
    for package_json_path in package_json_files:
        current_package = _load_json(package_json_path)
        if not current_package:
            continue
        current_deps = {
            **current_package.get("dependencies", {}),
            **current_package.get("devDependencies", {}),
        }
        package_deps.update(current_deps)

    if package_deps:
        if "react" in package_deps:
            frameworks.append("react")
        if "vite" in package_deps:
            frameworks.append("vite")
        if "@playwright/test" in package_deps or "playwright" in package_deps:
            test_frameworks.append("playwright")
        if "cypress" in package_deps:
            test_frameworks.append("cypress")
        if "vitest" in package_deps:
            test_frameworks.append("vitest")
        if "jest" in package_deps:
            test_frameworks.append("jest")

    if pyproject.exists() or requirements.exists():
        frameworks.append("python")
        test_frameworks.append("pytest")

    suggested_command = _suggest_test_command(package_json, test_frameworks)
    return {
        "repo_path": str(root),
        "frameworks": sorted(set(frameworks)),
        "test_frameworks": sorted(set(test_frameworks)),
        "suggested_test_command": suggested_command,
        "files": files[:80],
        "summary": _summarize_repo(root, files, package_deps),
    }


def propose_test_file(repo_path: str, instruction: str, output_mode: str = "playwright") -> dict:
    scan = scan_repo(repo_path)
    root = Path(scan["repo_path"])
    relative_path = _suggest_test_path(scan, output_mode)
    content = _build_test_skeleton(scan, instruction, output_mode)
    target = _safe_target(root, relative_path)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    diff = _make_diff(existing, content, str(relative_path))
    return {
        "repo_path": str(root),
        "relative_path": str(relative_path),
        "content": content,
        "diff": diff,
        "exists": target.exists(),
        "scan": scan,
    }


def write_proposed_file(repo_path: str, relative_path: str, content: str, approved: bool, allow_overwrite: bool = False) -> dict:
    if not approved:
        raise ValueError("Write requires explicit approval.")

    root = resolve_repo_path(repo_path)
    target = _safe_target(root, Path(relative_path))
    if target.exists() and not allow_overwrite:
        raise ValueError("Target file already exists. Enable overwrite to replace it.")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"written": True, "path": str(target), "relative_path": str(target.relative_to(root))}


def run_repo_tests(repo_path: str, command: str) -> dict:
    root = resolve_repo_path(repo_path)
    normalized = " ".join(shlex.split(command))
    if normalized not in ALLOWED_TEST_COMMANDS:
        raise ValueError(f"Command is not allowlisted. Allowed: {', '.join(sorted(ALLOWED_TEST_COMMANDS))}")

    completed = subprocess.run(
        shlex.split(normalized),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=settings.repo_command_timeout_seconds,
        check=False,
    )
    return {
        "command": normalized,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-12_000:],
        "stderr": completed.stderr[-12_000:],
    }


def _list_interesting_files(root: Path) -> list[str]:
    ignored = {".git", "node_modules", ".venv", "dist", "build", "__pycache__", ".pytest_cache"}
    files = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [item for item in dirs if item not in ignored]
        base = Path(current_root)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".py", ".feature", ".json", ".toml", ".md"}:
                files.append(str(path.relative_to(root)))
    return sorted(files)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _suggest_test_command(package_json: dict, test_frameworks: list[str]) -> str:
    scripts = package_json.get("scripts", {}) if package_json else {}
    if "test" in scripts:
        return "npm test"
    if "playwright" in test_frameworks:
        return "npx playwright test"
    if "pytest" in test_frameworks:
        return "python -m pytest"
    return "npm test"


def _summarize_repo(root: Path, files: list[str], package_deps: dict) -> str:
    parts = [f"Found {len(files)} interesting files in {root.name}."]
    if package_deps:
        parts.append(f"Detected Node dependencies: {', '.join(sorted(package_deps)[:8])}.")
    return " ".join(parts)


def _suggest_test_path(scan: dict, output_mode: str) -> Path:
    if output_mode == "gherkin":
        return Path("features/generated-ticket-workflow.feature")
    if output_mode == "playwright":
        return Path("tests/generated-workflow.spec.ts")
    if output_mode == "selenium":
        return Path("tests/generated/GeneratedWorkflowTest.java")
    if output_mode == "cypress" or "cypress" in scan["test_frameworks"]:
        return Path("cypress/e2e/generated-workflow.cy.js")
    if "python" in scan["frameworks"] and "pytest" in scan["test_frameworks"]:
        return Path("tests/test_generated_workflow.py")
    return Path("tests/generated-workflow.spec.ts")


def _build_test_skeleton(scan: dict, instruction: str, output_mode: str) -> str:
    header = f"// Generated proposal for {Path(scan['repo_path']).name}\n// Instruction: {instruction}\n\n"
    if output_mode == "gherkin":
        return "Feature: Generated workflow\n\n  Scenario: Proposed coverage\n    Given the application is ready\n    When the user performs the workflow from the ticket\n    Then the expected outcome should be verified\n"
    if output_mode == "selenium":
        return "import org.junit.jupiter.api.Test;\n\nclass GeneratedWorkflowTest {\n    @Test\n    void generatedWorkflow() {\n        // TODO: Implement Selenium steps from approved scenarios.\n    }\n}\n"
    if output_mode == "cypress":
        return f"{header}describe('generated workflow', () => {{\n  it('covers the approved scenario', () => {{\n    // TODO: Visit app, perform steps, and assert expected result.\n  }})\n}})\n"
    if output_mode == "playwright":
        return f"{header}import {{ test, expect }} from '@playwright/test'\n\nconst appUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173'\n\ntest('QA assistant repo integration smoke test', async ({{ page }}) => {{\n  await page.goto(appUrl)\n\n  await expect(page.getByRole('heading', {{ name: 'Repo Integration' }})).toBeVisible()\n  await expect(page.getByText('Scan a local repo, preview a generated test file')).toBeVisible()\n  await expect(page.getByLabel('Message')).toBeVisible()\n  await expect(page.getByLabel('Output mode')).toBeVisible()\n  await expect(page.getByRole('button', {{ name: 'Scan repo' }})).toBeVisible()\n  await expect(page.getByRole('button', {{ name: 'Propose test file' }})).toBeVisible()\n}})\n"
    if "python" in scan["frameworks"] and "pytest" in scan["test_frameworks"]:
        return f"# Generated proposal\n# Instruction: {instruction}\n\n\ndef test_generated_workflow():\n    # TODO: Implement approved scenario assertions.\n    assert True\n"
    return f"{header}import {{ test, expect }} from '@playwright/test'\n\ntest('generated workflow', async ({{ page }}) => {{\n  // TODO: Navigate to the target page.\n  // TODO: Perform approved scenario steps.\n  await expect(page).toBeDefined()\n}})\n"


def _safe_target(root: Path, relative_path: Path) -> Path:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Target path must be a safe relative path.")
    target = (root / relative_path).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Target path escapes repository root.")
    return target


def _make_diff(existing: str, proposed: str, relative_path: str) -> str:
    return "".join(difflib.unified_diff(
        existing.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
    ))
