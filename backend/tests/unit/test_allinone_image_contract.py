from pathlib import Path


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


def test_allinone_uses_production_wsgi_server() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.allinone").read_text(encoding="utf-8")
    start_script = (REPO_ROOT / "docker" / "start-backend.sh").read_text(
        encoding="utf-8"
    )

    assert "ENV FLASK_ENV=production" in dockerfile
    assert "gunicorn" in start_script
    assert "python app.py" not in start_script


def test_ci_unit_job_skips_tests_that_require_a_live_server() -> None:
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "deckforge-migration-ci.yml"
    ).read_text(encoding="utf-8")
    backend_step = workflow.split("- name: Backend tests", 1)[1].split(
        "- name: Frontend dependencies", 1
    )[0]

    assert "SKIP_SERVICE_TESTS: 'true'" in backend_step
