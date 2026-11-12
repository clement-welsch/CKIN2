"""Background price refresh for the local dashboard."""

import subprocess
import sys
import threading
from pathlib import Path


class PriceRefresh:
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
            self.state = {"state": "running", "message": "Collecte Steam en cours… Vous pouvez continuer à consulter le dashboard."}
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
                1: ("partial", "Actualisation partielle : certains prix sont manquants, anciens ou leur collecte a échoué."),
            }.get(result.returncode, ("error", "Actualisation impossible : vérifiez les données ou une collecte déjà en cours."))
            detail = result.stdout + result.stderr
        except Exception as error:
            state, message, detail = "error", "Impossible de lancer la collecte Steam.", str(error)
        with self.lock:
            self.state = dict(state=state, message=message, detail=detail)


REFRESH_WIDGET = '''<section aria-label="Actualisation Steam">
<button id="steam-refresh" type="button">Mettre à jour les prix Steam</button>
<p>Collecte les prix de tout le portefeuille et enregistre le snapshot mensuel.</p>
<p id="steam-status" role="status" aria-live="polite"></p>
<details id="steam-details" hidden><summary>Détails de la collecte</summary><pre id="steam-log" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>
</section><script src="/steam-refresh.js"></script>'''
