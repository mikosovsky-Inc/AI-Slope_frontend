"use strict";
const panel = document.getElementById("video-state");
if (panel) {
  const initial = JSON.parse(panel.dataset.state);
  let dirty = false;
  let attempts = 0;
  const markDirty = event => {
    if (event.target.closest("form")) dirty = true;
  };
  document.addEventListener("input", markDirty);
  document.addEventListener("change", markDirty);
  async function pollVideo() {
    if (document.hidden) { setTimeout(pollVideo, 5000); return; }
    try {
      const response = await fetch(panel.dataset.url, {cache: "no-store", signal: AbortSignal.timeout(15000)});
      if (response.status === 401) { location.assign("/login"); return; }
      if (!response.ok) throw new Error();
      const state = await response.json();
      if (JSON.stringify(state) !== JSON.stringify(initial)) {
        if (!dirty) { location.reload(); return; }
        document.getElementById("poll-message").textContent = "Stan filmu zmienił się. Masz niezapisane zmiany — odśwież stronę po ich zachowaniu.";
        return;
      }
      if (++attempts < 120 && state.has_active_tasks) { setTimeout(pollVideo, 5000); return; }
      if (!state.has_active_tasks) return;
    } catch { /* Manual refresh remains available. */ }
    document.getElementById("poll-message").textContent = "Automatyczne odświeżanie zatrzymane. Odśwież stronę, aby sprawdzić wynik.";
  }
  if (initial.has_active_tasks) setTimeout(pollVideo, 3000);
}
