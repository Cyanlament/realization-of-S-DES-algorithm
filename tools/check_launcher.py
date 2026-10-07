"""Check the Windows BAT entry point, window creation and default encryption."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "offscreen"), default="windows")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence file")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("The BAT launcher test requires Windows")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = args.platform
    log_path = ROOT / "build/launcher_check.log"
    log_path.parent.mkdir(exist_ok=True)
    environment["SDES_LOG"] = str(log_path)
    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(ROOT / "run.bat"), "--smoke-test"],
        cwd=ROOT.parent, env=environment, input=b"\r\n", capture_output=True, timeout=30,
    )
    console = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    success = result.returncode == 0 and "SDES_LAUNCH_OK" in log
    report = {"passed": success, "platform": args.platform, "exit_code": result.returncode,
              "entry_point": "cmd.exe /d /c run.bat --smoke-test", "different_working_directory": True,
              "console": console, "startup_log": log}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
