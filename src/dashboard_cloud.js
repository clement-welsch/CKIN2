(() => {
  const button = document.getElementById('cloud-publish');
  const status = document.getElementById('cloud-status');
  async function check() {
    try {
      const response = await fetch('/api/cloud-publish', {cache: 'no-store'});
      if (!response.ok) throw new Error();
      const result = await response.json();
      button.disabled = result.state === 'running';
      status.textContent = result.message;
      if (button.disabled) setTimeout(check, 1500);
    } catch {
      button.disabled = false;
      status.textContent = 'Connexion interrompue. Rechargez la page pour vérifier la sauvegarde.';
    }
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    status.textContent = 'Démarrage de la sauvegarde…';
    try {
      const response = await fetch('/api/cloud-publish', {
        method: 'POST', headers: {'X-CKIN2-Refresh': '1'}
      });
      if (!response.ok && response.status !== 409) throw new Error();
      await check();
    } catch {
      button.disabled = false;
      status.textContent = 'Impossible de démarrer la sauvegarde. Rechargez la page et réessayez.';
    }
  });
  check();
})();
