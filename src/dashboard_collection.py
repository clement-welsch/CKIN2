"""Background price refresh for the local dashboard."""

import subprocess
import sys
import threading
from pathlib import Path


class PriceRefresh:
    running_message = "Collecte Steam en cours… Vous pouvez continuer à consulter le dashboard."

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.Lock()
        self.state = {"state": "idle", "message": ""}

    def status(self):
        with self.lock:
            return dict(self.state)

    def start(self):
        with self.lock:
            if self.state["state"] == "running":
                return False
            self.state = {"state": "running", "message": self.running_message}
            threading.Thread(target=self._run, daemon=True).start()
            return True

    def _run(self):
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("update_portfolio.py")),
                 "home", "--root", str(self.root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            state, message = {
                0: ("success", "Prix Steam mis à jour et snapshot mensuel enregistré."),
                1: ("partial", "Actualisation partielle : vérifiez la couverture des prix et la publication cloud dans les détails."),
            }.get(result.returncode, ("error", "Actualisation impossible : vérifiez les données ou une collecte déjà en cours."))
            detail = result.stdout + result.stderr
        except Exception as error:
            state, message, detail = "error", "Impossible de lancer la collecte Steam.", str(error)
        with self.lock:
            self.state = dict(state=state, message=message, detail=detail)


class CloudPublication(PriceRefresh):
    running_message = "Sauvegarde de l’inventaire dans le cloud en cours…"

    def _run(self):
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("google_drive_cloud.py")),
                 "publish", "--root", str(self.root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300,
            )
            if result.returncode == 0:
                message = ("Inventaire sauvegardé sur Google Drive." if "Google Drive upload confirmed" in result.stdout
                           else "Archive prête dans le dossier cloud. Attendez la fin de synchronisation de votre application.")
                state = "success"
            else:
                state, message = "error", "Sauvegarde impossible : vérifiez la connexion cloud ou attendez la fin d’une mise à jour en cours."
        except Exception:
            state, message = "error", "Sauvegarde interrompue. Vérifiez votre connexion puis réessayez."
        # Never expose child-process output: provider errors can contain private URLs.
        with self.lock:
            self.state = dict(state=state, message=message)


REFRESH_WIDGET = '''<section aria-label="Actualisation Steam">
<button id="steam-refresh" type="button">Mettre à jour les prix Steam</button>
<p>Collecte les prix de tout le portefeuille et enregistre le snapshot mensuel.</p>
<p id="steam-status" role="status" aria-live="polite"></p>
<details id="steam-details" hidden><summary>Détails de la collecte</summary><pre id="steam-log" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>
</section><section aria-label="Sauvegarde cloud">
<button id="cloud-publish" type="button">Copier l’inventaire dans le cloud</button>
<p>Envoie une copie de l’inventaire et de son historique déjà enregistrés, sans collecter de nouveaux prix.</p>
<p id="cloud-status" role="status" aria-live="polite"></p>
<a href="/cloud-setup">Configurer Google Drive ou consulter le tutoriel</a>
</section><script src="/steam-refresh.js"></script><script src="/cloud-publish.js"></script>'''
