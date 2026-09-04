"""Exercise the actual runtime tool embedded in the workflow, using synthetic data."""

import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml


@pytest.fixture
def ci_redactor():
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/api-test.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["api-smoke"]["steps"]
    creation = next(step for step in steps if step["name"] == "Create temporary CI redactor")
    tree = ast.parse(creation["run"])
    source = next(
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "source" for target in node.targets)
    )
    namespace = {"__name__": "ci_redactor_test"}
    exec(compile(source, "ci_redact.py", "exec"), namespace)
    # Never consult the developer's or CI job's actual secret values in these tests.
    namespace["os"] = SimpleNamespace(environ={})
    return namespace, source, steps


@pytest.mark.parametrize(
    "field", ("password", "passwd", "token", "access_token", "refresh_token",
              "Authorization", "secret", "api_key"),
)
def test_ci_validation_json_redacts_sensitive_input(ci_redactor, field: str) -> None:
    namespace, _, _ = ci_redactor
    raw = {"detail": [{"input": "B1_CI_SYNTHETIC_VALUE", "loc": ["body", field]}]}
    assert "B1_CI_SYNTHETIC_VALUE" in json.dumps(raw)
    clean = namespace["redact_json"](raw)
    assert clean["detail"][0]["input"] == "[REDACTED]"
    assert "B1_CI_SYNTHETIC_VALUE" not in json.dumps(clean)


@pytest.mark.parametrize("representation", ("json", "pretty_json", "repr", "escaped_json"))
def test_ci_validation_stream_and_allure_trace_are_redacted(ci_redactor, representation: str) -> None:
    namespace, _, _ = ci_redactor
    raw = {"detail": [{"input": "B1_STREAM_SYNTHETIC_VALUE", "loc": ["body", "password"]},
                      {"loc": ["body", "username"], "input": "visible_username"}]}
    representations = {
        "json": json.dumps(raw), "pretty_json": json.dumps(raw, indent=2),
        "repr": repr(raw), "escaped_json": json.dumps(json.dumps(raw)),
    }
    trace = "HTTP Response " + representations[representation]
    assert "B1_STREAM_SYNTHETIC_VALUE" in trace
    clean = namespace["redact"](trace)
    assert "B1_STREAM_SYNTHETIC_VALUE" not in clean
    assert "[REDACTED]" in clean
    assert "visible_username" in clean
    allure = namespace["redact_json"]({"statusDetails": {"message": trace, "trace": trace}})
    assert "B1_STREAM_SYNTHETIC_VALUE" not in json.dumps(allure)


def test_ci_keeps_non_sensitive_validation_data(ci_redactor) -> None:
    namespace, _, _ = ci_redactor
    raw = {"loc": ["body", "username"], "input": "abc"}
    assert namespace["redact_json"](raw) == raw
    assert namespace["redact"](json.dumps(raw)) == json.dumps(raw)


def test_ci_existing_secret_rules_and_known_values_are_preserved(ci_redactor) -> None:
    namespace, _, _ = ci_redactor
    namespace["os"].environ.update(DB_PASSWORD="SYNTHETIC_DB_VALUE", JWT_SECRET_KEY="SYNTHETIC_KEY_VALUE")
    values = ("SYNTHETIC_DB_VALUE", "SYNTHETIC_KEY_VALUE", "synthetic.jwt.value", "B1_DIRECT_VALUE")
    raw = "Authorization: Bearer synthetic.jwt.value\npassword=B1_DIRECT_VALUE\n" + " ".join(values[:2])
    assert all(value in raw for value in values)
    clean = namespace["redact"](raw)
    assert all(value not in clean for value in values)


def test_ci_artifact_masks_validation_inputs_and_keeps_allure_structure(ci_redactor, tmp_path) -> None:
    namespace, _, _ = ci_redactor
    workspace = tmp_path / "workspace"
    temporary = tmp_path / "runner"
    results = workspace / "api-automation-framework/allure-results/full"
    results.mkdir(parents=True)
    temporary.mkdir()
    namespace["os"].environ.update(GITHUB_WORKSPACE=str(workspace), RUNNER_TEMP=str(temporary))
    raw = {"loc": ["body", "password"], "input": "B1_ARTIFACT_SYNTHETIC_VALUE"}
    result = {"uuid": "synthetic-result", "statusDetails": {"trace": json.dumps(raw)},
              "attachments": [{"name": "HTTP Response", "source": "response-attachment.json", "type": "application/json"}]}
    # Synthetic fixtures only; never upload this raw temporary workspace.
    (results / "case-result.json").write_text(json.dumps(result), encoding="utf-8")
    (results / "case-container.json").write_text(json.dumps({"children": ["synthetic-result"]}), encoding="utf-8")
    (results / "response-attachment.json").write_text(json.dumps({"detail": [raw]}), encoding="utf-8")
    (results / "trace.txt").write_text(repr(raw), encoding="utf-8")
    assert "B1_ARTIFACT_SYNTHETIC_VALUE" in (results / "response-attachment.json").read_text(encoding="utf-8")

    namespace["artifacts"]()

    safe = temporary / "ci-artifacts-safe/api-automation-framework/allure-results/full"
    assert len(list(safe.iterdir())) == 4
    for path in safe.iterdir():
        assert "B1_ARTIFACT_SYNTHETIC_VALUE" not in path.read_text(encoding="utf-8")
    clean = json.loads((safe / "response-attachment.json").read_text(encoding="utf-8"))
    assert clean["detail"][0]["input"] == "[REDACTED]"
    clean_result = json.loads((safe / "case-result.json").read_text(encoding="utf-8"))
    assert clean_result["attachments"] == result["attachments"]


def test_ci_stream_error_is_fail_closed_and_upload_gate_is_preserved(ci_redactor) -> None:
    namespace, source, steps = ci_redactor
    # Exercise the CLI entrypoint without writing a helper file or inheriting secrets.
    result = subprocess.run([sys.executable, "-B", "-c", source, "stream"],
                            input=b"\x00B1_UNSAFE_OUTPUT", capture_output=True, env={}, check=False)
    assert result.returncode != 0
    assert result.stdout == b""
    assert b"B1_UNSAFE_OUTPUT" not in result.stderr
    upload = next(step for step in steps if step["name"] == "Upload test artifacts")
    assert upload["if"] == "always() && steps.sanitize.outcome == 'success'"
    assert upload["with"]["path"] == "${{ runner.temp }}/ci-artifacts-safe"
    assert all("ci_redact.py" in step["run"] for step in steps if step["name"] in
               ("Run test server tests", "Run smoke tests", "Run full tests"))


def test_ci_stream_cli_redacts_validation_json(ci_redactor) -> None:
    _, source, _ = ci_redactor
    raw = {"loc": ["body", "password"], "input": "B1_CLI_SYNTHETIC_VALUE"}
    result = subprocess.run(
        [sys.executable, "-B", "-c", source, "stream"],
        input=json.dumps(raw).encode(), capture_output=True, env={}, check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["input"] == "[REDACTED]"
    assert b"B1_CLI_SYNTHETIC_VALUE" not in result.stdout + result.stderr


def test_ci_invalid_json_artifact_fails_instead_of_copying_raw(ci_redactor, tmp_path) -> None:
    namespace, _, _ = ci_redactor
    workspace = tmp_path / "workspace"
    temporary = tmp_path / "runner"
    results = workspace / "api-automation-framework/allure-results/full"
    results.mkdir(parents=True)
    temporary.mkdir()
    namespace["os"].environ.update(GITHUB_WORKSPACE=str(workspace), RUNNER_TEMP=str(temporary))
    (results / "invalid.json").write_text("{B1_UNSAFE_JSON", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        namespace["artifacts"]()

    safe = temporary / "ci-artifacts-safe"
    assert not (safe / "sanitization-summary.json").exists()
    assert not list(safe.rglob("invalid.json"))
