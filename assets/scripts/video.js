"use strict";
const panel = document.getElementById("video-state");
if (panel) {
  const message = document.getElementById("poll-message");
  const stopped = "Automatyczne odświeżanie zatrzymane. Odśwież stronę, aby sprawdzić wynik.";
  function valid(state) {
    return state && typeof state.status === "string" && state.status.length > 0
      && typeof state.updated_at === "string"
      && typeof state.has_active_tasks === "boolean" && Array.isArray(state.tasks)
      && state.tasks.every(task => task && typeof task.id === "string"
        && typeof task.kind === "string" && typeof task.status === "string"
        && Number.isInteger(task.attempts));
  }
  let initial;
  try { initial = JSON.parse(panel.dataset.state); } catch { initial = null; }
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
      if (!valid(state)) throw new Error();
      if (JSON.stringify(state) !== JSON.stringify(initial)) {
        if (!dirty) { location.reload(); return; }
        document.getElementById("poll-message").textContent = "Stan filmu zmienił się. Masz niezapisane zmiany — odśwież stronę po ich zachowaniu.";
        return;
      }
      if (++attempts < 120 && state.has_active_tasks) { setTimeout(pollVideo, 5000); return; }
      if (!state.has_active_tasks) return;
    } catch { /* Manual refresh remains available. */ }
    message.textContent = stopped;
  }
  if (!valid(initial)) message.textContent = stopped;
  else if (initial.has_active_tasks) setTimeout(pollVideo, 3000);
}
