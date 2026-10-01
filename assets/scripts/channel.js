"use strict";
const task = document.getElementById("analysis-task");
if (task && ["queued", "running"].includes(task.dataset.status)) {
  let attempts = 0;
  let dirty = false;
  const markDirty = event => {
    if (event.target.closest("form")) dirty = true;
  };
  document.addEventListener("input", markDirty);
  document.addEventListener("change", markDirty);
  async function poll() {
    if (document.hidden) { setTimeout(poll, 5000); return; }
    try {
      const response = await fetch(task.dataset.statusUrl, {cache: "no-store", signal: AbortSignal.timeout(15000)});
      if (response.status === 401) { location.assign("/login"); return; }
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (!data || typeof data.status !== "string") throw new Error();
      if (["succeeded", "failed", "needs_review"].includes(data.status)) {
        if (dirty) {
          document.getElementById("task-message").textContent = "Stan zadania zmienił się. Masz niezapisane zmiany — odśwież stronę po ich zachowaniu.";
          return;
        }
        location.reload(); return;
      }
      if (!["queued", "running"].includes(data.status)) throw new Error();
      document.getElementById("task-message").textContent = `Stan zadania: ${data.status}`;
      if (++attempts < 120) { setTimeout(poll, 5000); return; }
    } catch { /* Keep the manual refresh link usable. */ }
    document.getElementById("task-message").textContent = "Automatyczne odświeżanie zatrzymane. Użyj odświeżenia, aby sprawdzić wynik.";
  }
  setTimeout(poll, 3000);
}
