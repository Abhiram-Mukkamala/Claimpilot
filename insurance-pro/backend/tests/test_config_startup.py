import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
CONFIG_FILE = BACKEND / "app" / "core" / "config.py"
REQUIRED_SETTINGS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET",
)
DUMMY_SETTINGS = {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}
LOAD_CONFIG = (
    "import importlib.util, os, sys; "
    "spec = importlib.util.spec_from_file_location('isolated_config', os.environ['CONFIG_FILE']); "
    "module = importlib.util.module_from_spec(spec); "
    "sys.modules[spec.name] = module; "
    "spec.loader.exec_module(module); "
    "print('configuration-loaded')"
)


def _run_config_import(tmp_path, env):
    env["CONFIG_FILE"] = str(CONFIG_FILE)
    return subprocess.run(
        [sys.executable, "-c", LOAD_CONFIG],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_startup_reports_missing_required_setting_names(tmp_path):
    env = os.environ.copy()
    for name in REQUIRED_SETTINGS:
        env.pop(name, None)
        env.pop(name.lower(), None)
    result = _run_config_import(tmp_path, env)

    assert result.returncode != 0
    assert "Invalid or missing configuration variable(s)" in result.stderr
    missing_names = {name for name in REQUIRED_SETTINGS if name in result.stderr}
    assert missing_names == set(REQUIRED_SETTINGS)


def test_startup_accepts_dummy_required_settings(tmp_path):
    env = os.environ.copy()
    env.update(DUMMY_SETTINGS)
    result = _run_config_import(tmp_path, env)

    assert result.returncode == 0, "Configuration import failed with dummy required settings"
    assert result.stdout.strip() == "configuration-loaded"
