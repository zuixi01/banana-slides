from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_allinone_image_normalizes_shell_scripts_before_startup() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.allinone").read_text(encoding="utf-8")

    copy_index = dockerfile.index("COPY docker/ ./docker/")
    normalize_index = dockerfile.index("sed -i 's/\\r$//' /app/docker/*.sh")
    command_index = dockerfile.index('CMD ["/usr/bin/supervisord"')

    assert copy_index < normalize_index < command_index


def test_shell_scripts_are_declared_lf_in_git() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "*.sh text eol=lf" in attributes.splitlines()


def test_allinone_routes_all_health_contracts_to_backend() -> None:
    nginx = (REPO_ROOT / "docker" / "nginx-allinone.conf").read_text(
        encoding="utf-8"
    )

    for path in ("/health", "/health/model", "/live", "/ready"):
        assert f"location = {path} {{" in nginx


def test_nginx_upload_limits_match_the_backend_contract() -> None:
    """Both container layouts must allow the 200 MB advertised by the UI/API."""
    for relative_path in (
        Path("docker/nginx-allinone.conf"),
        Path("frontend/nginx.conf"),
    ):
        nginx = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        match = re.search(r"client_max_body_size\s+(\d+)M;", nginx)

        assert match, f"missing client_max_body_size in {relative_path}"
        assert int(match.group(1)) >= 200, (
            f"{relative_path} must not reject uploads accepted by Flask"
        )


def test_allinone_uses_production_wsgi_server() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.allinone").read_text(encoding="utf-8")
    start_script = (REPO_ROOT / "docker" / "start-backend.sh").read_text(
        encoding="utf-8"
    )

    assert "ENV FLASK_ENV=production" in dockerfile
    assert "gunicorn" in start_script
    assert "python app.py" not in start_script


def test_allinone_declares_durable_runtime_paths() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.allinone").read_text(encoding="utf-8")
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert 'VOLUME ["/app/backend/instance", "/app/uploads"]' in dockerfile
    assert "**/instance/*.db" in dockerignore


def test_ci_unit_job_skips_tests_that_require_a_live_server() -> None:
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "deckforge-migration-ci.yml"
    ).read_text(encoding="utf-8")
    backend_step = workflow.split("- name: Backend tests", 1)[1].split(
        "- name: Frontend dependencies", 1
    )[0]

    assert "SKIP_SERVICE_TESTS: 'true'" in backend_step
