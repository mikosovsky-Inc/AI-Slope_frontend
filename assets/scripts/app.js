"use strict";
// Remove credentials left by the previous browser-to-backend implementation.
try { sessionStorage.removeItem("ai-slop.access-token"); } catch { /* Storage disabled. */ }
const toggle = document.getElementById("toggle-password");
if (toggle) {
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    const input = document.getElementById("password");
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    toggle.textContent = visible ? "UKRYJ" : "POKAŻ";
    toggle.setAttribute("aria-pressed", String(visible));
    toggle.setAttribute("aria-label", visible ? "Ukryj hasło" : "Pokaż hasło");
  });
}

const message = document.getElementById("form-message");
if (message && !message.hidden) message.focus();

for (const form of document.querySelectorAll("form[method=post]")) {
  const submit = form.querySelector("button[type=submit]");
  if (!submit) continue;
  const label = submit.textContent;
  const initiallyDisabled = submit.disabled;
  // Invalid events do not bubble. Show a persistent explanation in addition
  // to the browser tooltip, including when autofill leaves a field empty.
  form.addEventListener("invalid", (event) => {
    const field = event.target;
    if (!message) return;
    const labels = { email: "adres e-mail", password: "hasło", confirm_password: "powtórzone hasło" };
    const name = labels[field.name] || "pole formularza";
    message.textContent = field.validity.valueMissing
      ? `Uzupełnij ${name}. Jeśli Safari podpowiada dane, zatwierdź ich uzupełnienie.`
      : `Sprawdź ${name}. ${field.validationMessage}`;
    message.hidden = false;
  }, true);
  form.addEventListener("submit", () => {
    // Keep inputs enabled so native form submission includes their values.
    form.setAttribute("aria-busy", "true");
    submit.disabled = true;
    submit.textContent = form.action.endsWith("/login") ? "LOGOWANIE…" : "CHWILKA…";
  });
  window.addEventListener("pageshow", () => {
    form.removeAttribute("aria-busy");
    submit.disabled = initiallyDisabled;
    submit.textContent = label;
  });
}
