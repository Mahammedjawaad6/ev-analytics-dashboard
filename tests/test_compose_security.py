from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

if not (ROOT / "compose.yaml").is_file():
    pytest.skip(
        "Repository policy files are not included in the application image.",
        allow_module_level=True,
    )


def _service_block(service_name):
    lines = (ROOT / "compose.yaml").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {service_name}:") + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith("    "):
            break
        block.append(line)
    return block


def test_streamlit_port_is_published_on_loopback_only():
    dashboard = _service_block("dashboard")
    ports_index = dashboard.index("    ports:")
    port_lines = []
    for line in dashboard[ports_index + 1 :]:
        if not line.startswith("      - "):
            break
        port_lines.append(line.removeprefix("      - ").strip().strip("\"'"))

    assert port_lines == ["127.0.0.1:8501:8501"]
    assert "- --server.address=0.0.0.0" in [line.strip() for line in dashboard]


def test_dashboard_mounts_runtime_csv_read_only():
    dashboard = _service_block("dashboard")
    assert "      - type: bind" in dashboard
    assert "        source: ./EV data by country 2026.csv" in dashboard
    assert "        target: /data/ev-data.csv" in dashboard
    assert "        read_only: true" in dashboard


def test_private_input_and_outputs_are_excluded_from_git_and_docker_contexts():
    ignored_paths = {
        "output/": (ROOT / ".gitignore", ROOT / ".dockerignore"),
        "*.csv": (ROOT / ".gitignore", ROOT / ".dockerignore"),
        "*.ipynb": (ROOT / ".gitignore", ROOT / ".dockerignore"),
    }

    for pattern, files in ignored_paths.items():
        for path in files:
            rules = path.read_text(encoding="utf-8").splitlines()
            normalized_rules = {rule.rstrip("/") for rule in rules}
            assert pattern.rstrip("/") in normalized_rules, (
                f"{pattern} must remain excluded by {path.name}"
            )


def test_ci_workflow_grants_only_read_access_to_repository_contents():
    lines = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    ).splitlines()
    start = lines.index("permissions:") + 1
    permissions = []
    for line in lines[start:]:
        if not line.startswith("  "):
            break
        permissions.append(line.strip())

    assert permissions == ["contents: read"]
