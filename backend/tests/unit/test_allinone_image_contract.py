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
