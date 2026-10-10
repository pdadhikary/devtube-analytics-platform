import ast
import importlib
import sys
from pathlib import Path

CORE_PACKAGE_DIR = Path(__file__).parent.parent / "src" / "devtube_pipeline" / "core"

CORE_MODULES = [
    "devtube_pipeline.core.comments",
    "devtube_pipeline.core.playlists",
    "devtube_pipeline.core.raw_layout",
    "devtube_pipeline.core.thumbnails",
    "devtube_pipeline.core.transcripts",
    "devtube_pipeline.core.videos",
]

FORBIDDEN_IMPORTS = {
    "httpx",
    "boto3",
    "botocore",
    "pyiceberg",
    "yaml",
    "devtube_pipeline.settings",
    "devtube_pipeline.warehouse",
    "devtube_pipeline.youtube",
    "devtube_pipeline.assets",
}

SETTINGS_ENV_VARS = [
    "YOUTUBE_API_BASE",
    "YOUTUBE_API_KEY",
    "AWS_ENDPOINT_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION",
    "TF_VAR_S3_BUCKET_NAME",
    "TRANSCRIPT_LANGS",
    "TRANSCRIPT_SOURCES",
]


def imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_core_source_imports_nothing_forbidden() -> None:
    offenders: dict[str, set[str]] = {}
    for path in sorted(CORE_PACKAGE_DIR.glob("*.py")):
        bad = imported_modules(path.read_text()) & FORBIDDEN_IMPORTS
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"forbidden imports in core: {offenders}"


def test_core_modules_import_without_settings(monkeypatch) -> None:
    for var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    for name in CORE_MODULES:
        importlib.import_module(name)

    assert "devtube_pipeline.settings" not in sys.modules
