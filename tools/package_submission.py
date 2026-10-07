"""Package only deliverables; exclude local environments, builds and input PDF."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT / name for name in (
        ".editorconfig", ".gitattributes", ".gitignore", "README.md", "requirements.txt", "requirements-dev.txt", "main.py", "run.bat")]
    for directory in ("sdes", "reference", "tests", "tools", "docs", "evidence", "output/pdf", ".github"):
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    records = [{"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)]
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    (output / "submission_manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    package = output / "S-DES实验提交包.zip"
    with ZipFile(package, "w", ZIP_DEFLATED) as archive:
        for record in records:
            archive.write(ROOT / record["path"], record["path"])
        archive.writestr("SHA256SUMS.txt", "\n".join(f"{record['sha256']}  {record['path']}" for record in records) + "\n")
    with ZipFile(package) as archive:
        assert archive.testzip() is None
        for record in records:
            assert hashlib.sha256(archive.read(record["path"])).hexdigest() == record["sha256"]
    print(json.dumps({"files": len(records), "package_bytes": package.stat().st_size,
                      "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
