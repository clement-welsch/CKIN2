"""Explicit Google consent and private Drive uploads; no credentials in Git."""

import argparse
import getpass
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from cloud_inventory import ROOT, publish, write_state
from private_cloud_state import load_private, save_private

SCOPE = "https://www.googleapis.com/auth/drive.file"
API = "https://www.googleapis.com/drive/v3/files"
SECRET_PATH = "data/runtime/google-drive.secret"


def folder_id(value):
    value = value.strip()
    if value.startswith("https://"):
        parsed = urlsplit(value)
        match = re.fullmatch(r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)/*", parsed.path)
        if parsed.netloc != "drive.google.com" or not match:
            raise ValueError("Expected a Google Drive folder link")
        value = match[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        raise ValueError("Invalid Google Drive folder identifier")
    return value


def check_folder(session, identifier):
    response = session.get(f"{API}/{identifier}",
                           params={"fields": "mimeType,capabilities(canAddChildren),trashed", "supportsAllDrives": "true"},
                           timeout=30)
    if response.status_code != 200:
        raise ValueError("Google folder unavailable; select the intended folder during authorization")
    metadata = response.json()
    if (metadata.get("mimeType") != "application/vnd.google-apps.folder" or metadata.get("trashed")
            or metadata.get("capabilities", {}).get("canAddChildren") is not True):
        raise ValueError("Google account cannot upload into the selected folder")


def connect(root, client_secrets, target):
    from google_auth_oauthlib.flow import InstalledAppFlow

    identifier = folder_id(target)
    client = json.loads(Path(client_secrets).read_text(encoding="utf-8"))
    settings = client.get("installed", {})
    if (settings.get("auth_uri") not in ("https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth")
            or settings.get("token_uri") != "https://oauth2.googleapis.com/token"):
        raise ValueError("Use Google's downloaded OAuth client configuration for a Desktop app")
    flow = InstalledAppFlow.from_client_config(client, [SCOPE], autogenerate_code_verifier=True)
    # A private launcher is a fallback when Windows cannot open the default browser.
    root = Path(root).resolve()
    launcher = root / "data/runtime/google-connect.html"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    authorization_url = flow.authorization_url
    def prepare_authorization(**options):
        url, state = authorization_url(**options)
        with launcher.open("w", encoding="utf-8") as stream:
            os.chmod(launcher, 0o600)
            stream.write('<!doctype html><meta charset="utf-8"><title>Connexion CKIN2</title>'
                         '<meta http-equiv="refresh" content="0;url=' + html.escape(url, quote=True) + '">')
        print("If no browser opens, open the private file data/runtime/google-connect.html.", flush=True)
        return url, state
    flow.authorization_url = prepare_authorization
    try:
        credentials = flow.run_local_server(
            host="127.0.0.1", port=0, timeout_seconds=900,
            authorization_prompt_message="Complete the Google authorization in your browser.",
            success_message="Autorisation reçue. Vous pouvez fermer cette fenêtre et revenir à CKIN2.",
            prompt="consent", trigger_onepick="true", allow_folder_selection="true", file_ids=identifier)
    finally:
        launcher.unlink(missing_ok=True)
    if not credentials.refresh_token:
        raise ValueError("Google did not grant offline access; connect again")
    with flow.authorized_session() as session:
        check_folder(session, identifier)
    save_private(root / SECRET_PATH, {"folder_id": identifier, "credentials": json.loads(credentials.to_json())})
    write_state(root / "data/runtime/cloud-config.json", {"enabled": True, "provider": "google_drive"})


def upload_archive(session, archive, identifier):
    """Confirm upload metadata and checksum before reporting remote success."""
    archive = Path(archive)
    check_folder(session, identifier)
    response = session.post("https://www.googleapis.com/upload/drive/v3/files",
                            params={"uploadType": "resumable", "fields": "id,md5Checksum,size", "supportsAllDrives": "true"},
                            json={"name": archive.name, "parents": [identifier]},
                            headers={"X-Upload-Content-Type": "application/zip",
                                     "X-Upload-Content-Length": str(archive.stat().st_size)},
                            timeout=30, allow_redirects=False)
    location = response.headers.get("Location", "")
    endpoint = urlsplit(location)
    if (response.status_code not in (200, 201) or endpoint.scheme != "https"
            or endpoint.netloc != "www.googleapis.com" or not endpoint.path.startswith("/upload/drive/")):
        raise ValueError("Google could not start the upload; retry publication")
    with archive.open("rb") as content:
        response = session.put(location, data=content, headers={"Content-Type": "application/zip"},
                               timeout=120, allow_redirects=False)
    if response.status_code not in (200, 201):
        raise ValueError("Google upload incomplete; retry publication")
    metadata = response.json()
    checksum = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    if (not metadata.get("id") or metadata.get("md5Checksum") != checksum
            or str(metadata.get("size")) != str(archive.stat().st_size)):
        raise ValueError("Google upload verification failed; retry publication")


def publish_google(root):
    # Exceptions deliberately omit provider responses, private URLs and tokens.
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.credentials import Credentials

        root = Path(root)
        state = load_private(root / SECRET_PATH)
        credentials = Credentials.from_authorized_user_info(state["credentials"], [SCOPE])
        with tempfile.TemporaryDirectory(prefix="ckin2-drive-") as staging:
            archive = publish(root, staging)
            with AuthorizedSession(credentials) as session:
                upload_archive(session, archive, folder_id(state["folder_id"]))
        state["credentials"] = json.loads(credentials.to_json())
        save_private(root / SECRET_PATH, state)
    except Exception:
        raise ValueError("Google Drive publication failed. Check your connection or reconnect Google; local data is preserved.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["connect", "disconnect", "publish"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--client-secrets", type=Path)
    args = parser.parse_args(argv)
    try:
        from collection_runtime import collection_lock
        with collection_lock(args.root):
            if args.command == "connect":
                if args.client_secrets is None:
                    parser.error("--client-secrets is required for connect")
                pending = args.root / "data/runtime/google-drive-target.secret"
                target = (load_private(pending)["folder_id"] if pending.exists() else
                          getpass.getpass("Lien du dossier Google Drive (saisie masquée) : "))
                connect(args.root, args.client_secrets, target)
                print("Google connected. Automatic publication is enabled.")
            elif args.command == "disconnect":
                write_state(args.root / "data/runtime/cloud-config.json", {"enabled": False})
                (args.root / SECRET_PATH).unlink(missing_ok=True)
                print("Local Google authorization removed. Revoke CKIN2 in your Google account to revoke remote access too.")
            else:
                from cloud_inventory import auto_publish
                return 1 if auto_publish(args.root)["status"] in ("failed", "disabled") else 0
    except Exception as error:
        if type(error).__name__ == "WSGITimeoutError":
            parser.exit(2, "Google connection timed out. Run connect again and finish the browser steps within 15 minutes.\n")
        parser.exit(2, "Google operation failed. Check local setup and Google authorization; no private details were logged.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
