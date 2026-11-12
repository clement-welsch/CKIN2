(() => {
  const button = document.getElementById('steam-refresh');
  const status = document.getElementById('steam-status');
  let running = false;
  async function check() {
    try {
      const response = await fetch('/api/steam-refresh', {cache: 'no-store'});
      if (!response.ok) throw new Error();
      const result = await response.json();
      button.disabled = result.state === 'running';
      status.textContent = result.message;
      document.getElementById('steam-details').hidden = !result.detail;
      document.getElementById('steam-log').textContent = result.detail || '';
      if (result.state === 'running') {
        running = true;
        setTimeout(check, 1500);
      } else if (running) {
        location.reload();
      }
    } catch {
      button.disabled = false;
      status.textContent = 'Connexion au dashboard interrompue. Rechargez la page pour vérifier la collecte.';
    }
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const response = await fetch('/api/steam-refresh', {method: 'POST', headers: {'X-CKIN2-Refresh': '1'}});
      if (!response.ok && response.status !== 409) throw new Error();
      running = true;
      await check();
    } catch {
      button.disabled = false;
      status.textContent = 'Impossible de démarrer la collecte. Rechargez la page pour vérifier son état.';
    }
  });
  check();
})();
