"""Publish portable data snapshots through a cloud-synced folder, or restore one."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def publish(root, folder):
    """Write a unique, complete archive; the sync client handles cloud upload."""
    root, folder = Path(root).resolve(), Path(folder).resolve()
    source = root / "data/processed"
    if folder.is_relative_to(root / "data"):
        raise ValueError("Cloud folder must be outside the source data directory")
    files = sorted(source.rglob("*.csv"))
    if not files:
        raise ValueError("No processed CSV files to publish")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    name = f"ckin2-{stamp.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}.zip"
    # Build outside the sync folder: clients never see a partially written ZIP.
    with tempfile.TemporaryDirectory(prefix="ckin2-publish-") as staging:
        archive = Path(staging) / name
        manifest = {"version": 1, "published_at": stamp.isoformat(), "files": {}}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                if path.is_symlink() or not path.resolve().is_relative_to(source):
                    raise ValueError("Linked data files are not supported")
                content = path.read_bytes()
                relative = path.relative_to(root).as_posix()
                manifest["files"][relative] = hashlib.sha256(content).hexdigest()
                bundle.writestr(relative, content)
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        temporary = folder / (name + ".partial")
        try:
            shutil.copyfile(archive, temporary)
            temporary.replace(folder / name)
        finally:
            temporary.unlink(missing_ok=True)
    return folder / name


def restore(archive, destination):
    """Verify all files before creating a new data root; never overwrite a root."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new folder")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        manifest = json.loads(bundle.read("manifest.json"))
        files = manifest.get("files")
        if manifest.get("version") != 1 or not isinstance(files, dict) or not files:
            raise ValueError("Unsupported or empty manifest")
        if set(names) != {"manifest.json", *files}:
            raise ValueError("Archive contents do not match manifest")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ckin2-restore-", dir=destination.parent) as staging:
            for name, digest in files.items():
                path = PurePosixPath(name)
                if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                        or path.parts[:2] != ("data", "processed") or path.suffix != ".csv"):
                    raise ValueError("Invalid archive data path")
                content = bundle.read(name)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise ValueError("Archive checksum mismatch")
                target = Path(staging).joinpath(*path.parts)
                if target.exists():
                    raise ValueError("Colliding archive paths")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            (Path(staging) / "cloud_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            # mkdir is exclusive, including if another process created the root meanwhile.
            destination.mkdir()
            try:
                shutil.move(str(Path(staging) / "data"), str(destination / "data"))
                shutil.move(str(Path(staging) / "cloud_manifest.json"), str(destination / "cloud_manifest.json"))
            except BaseException:
                shutil.rmtree(destination)
                raise
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    upload = commands.add_parser("publish", help="Create an archive in a synced cloud folder")
    upload.add_argument("--root", type=Path, default=ROOT)
    upload.add_argument("--folder", type=Path, required=True)
    download = commands.add_parser("restore", help="Restore a downloaded ZIP into a new folder")
    download.add_argument("archive", type=Path)
    download.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "publish":
            print(publish(args.root, args.folder))
            print("Archive ready. Wait for your cloud client to confirm upload before leaving.")
        else:
            print(restore(args.archive, args.destination))
            print("Snapshot restored. Publication time is recorded in cloud_manifest.json.")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(2, f"Cloud snapshot failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
