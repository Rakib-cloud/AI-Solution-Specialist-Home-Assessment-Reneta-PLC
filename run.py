"""Start the Leave Policy Assistant.

On the first run this creates a .venv beside the project, installs the
dependencies into it, and hands over to that interpreter. After that it just
starts the app. Works the same on macOS, Linux and Windows.

    python run.py

Set SKIP_BOOTSTRAP=1 to manage the environment yourself.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PYTHON = (3, 9)
PACKAGES = ("flask", "dotenv", "pdfplumber", "reportlab", "pypdf")


def venv_python() -> Path:
    """The interpreter inside .venv, wherever this platform puts it."""
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def have_packages(python: Path | None = None) -> bool:
    probe = "import " + ", ".join(PACKAGES)
    if python is None:
        try:
            exec(compile(probe, "<probe>", "exec"), {})
        except ImportError:
            return False
        return True
    if not python.exists():
        return False
    return subprocess.run([str(python), "-c", probe], capture_output=True).returncode == 0


def create_venv() -> None:
    import venv

    print(f"Creating a virtual environment in {VENV.name} ...", flush=True)
    try:
        venv.EnvBuilder(with_pip=True).create(VENV)
    except Exception as error:  # ensurepip is missing on some Linux builds
        sys.exit(
            f"\nCould not create a virtual environment: {error}\n"
            "On Debian or Ubuntu, install it first:\n"
            "    sudo apt install python3-venv\n"
        )


def install(python: Path) -> None:
    print("Installing dependencies, this takes a minute the first time ...", flush=True)
    try:
        subprocess.check_call(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
             "-r", str(REQUIREMENTS)]
        )
    except subprocess.CalledProcessError:
        sys.exit(
            "\nThe dependencies could not be installed. Check your internet connection, "
            "or install them by hand:\n"
            f"    {python} -m pip install -r requirements.txt\n"
        )


def bootstrap() -> int:
    """Prepare .venv, then run this script again with that interpreter."""
    if sys.version_info < MIN_PYTHON:
        sys.exit(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required. "
            f"This is {sys.version.split()[0]}."
        )

    python = venv_python()
    if not python.exists():
        create_venv()
    if not have_packages(python):
        install(python)

    print("Starting the app ...\n", flush=True)
    child = {**os.environ, "BOOTSTRAPPED": "1"}
    try:
        return subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]], env=child).returncode
    except KeyboardInterrupt:
        return 0


def serve() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    from app import create_app

    port = int(os.environ.get("PORT", "5050"))
    # the debug reloader runs this file again; only the first process announces itself
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print(f"  Leave Policy Assistant  ->  http://127.0.0.1:{port}\n", flush=True)
    create_app().run(host="127.0.0.1", port=port, debug=True)


if __name__ == "__main__":
    if have_packages() or os.environ.get("SKIP_BOOTSTRAP") == "1":
        serve()
    else:
        raise SystemExit(bootstrap())
