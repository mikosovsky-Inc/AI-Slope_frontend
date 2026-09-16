"use strict";

const $ = (id) => document.getElementById(id);
const TOKEN_KEY = "ai-slop.access-token";
let token = null;
try { token = sessionStorage.getItem(TOKEN_KEY); } catch { /* In-memory session still works. */ }
let mode = "login";
let firstAccount = false;
let busy = false;
let expiryTimer;
let apiBaseUrl;

function saveToken(value) {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* Storage can be disabled by the browser. */ }
}

function showMessage(text, success = false) {
  $("message").textContent = text;
  $("message").classList.toggle("success", success);
  $("message").hidden = !text;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${apiBaseUrl}/api/v1/auth${path}`, {
      ...options, cache: "no-store", signal: AbortSignal.timeout(15000),
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Nie udało się połączyć ze studiem. Sprawdź połączenie i spróbuj ponownie.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const messages = {
      401: "Nieprawidłowy e-mail lub hasło. Spróbuj ponownie.",
      409: "Ten e-mail ma już konto. Przejdź do logowania.",
      422: "Sprawdź adres e-mail i hasło. Nowe hasło musi mieć od 12 do 128 znaków.",
      429: "Zbyt wiele prób. Poczekaj chwilę i spróbuj ponownie.",
    };
    const error = new Error(messages[response.status] || "Studio jest chwilowo niedostępne. Spróbuj ponownie za moment.");
    error.status = response.status;
    throw error;
  }
  return body;
}

function setMode(next, initial = false) {
  mode = next;
  const register = mode === "register";
  $("loading-view").hidden = true;
  $("auth-view").hidden = false;
  $("account-view").hidden = true;
  $("retry-button").hidden = true;
  $("step-label").textContent = register ? "SYSTEM / NEW PLAYER" : "SYSTEM / WELCOME BACK";
  $("form-kicker").textContent = register && firstAccount ? "PIERWSZY GRACZ. PIERWSZY KROK." : "TWOJE MIEJSCE NA DOBRE POMYSŁY";
  $("form-title").textContent = register ? (firstAccount ? "Zacznij swoje studio." : "Dołącz do studia.") : "Witaj ponownie.";
  $("form-description").textContent = register ? "Załóż konto. Daj swoim pomysłom nowy format." : "Zaloguj się i wróć do swoich pomysłów.";
  $("setup-note").hidden = !(register && firstAccount);
  $("confirm-field").hidden = !register;
  $("confirm-password").required = register;
  $("confirm-password").disabled = !register;
  $("password").minLength = register ? 12 : 1;
  $("password").autocomplete = register ? "new-password" : "current-password";
  $("password").type = "password";
  $("password").value = "";
  $("confirm-password").value = "";
  $("toggle-password").textContent = "POKAŻ";
  $("toggle-password").setAttribute("aria-pressed", "false");
  $("toggle-password").setAttribute("aria-label", "Pokaż hasło");
  $("password-hint").textContent = register ? "12–128 znaków. Dobry pomysł zaczyna się od dobrego hasła." : "Twoje hasło do studia.";
  $("submit-label").textContent = register ? "UTWÓRZ KONTO" : "WEJDŹ DO STUDIA";
  $("switch-line").hidden = firstAccount;
  $("switch-copy").textContent = register ? "Masz już konto?" : "Nie masz jeszcze konta?";
  $("switch-link").textContent = register ? "Zaloguj się ↗" : "Załóż konto ↗";
  $("switch-link").href = register ? "/login" : "/register";
  document.title = `${register ? "Rejestracja" : "Logowanie"} — AI-Slop`;
  history.replaceState(null, "", register ? "/register" : "/login");
  showMessage("");
  if (!initial) $("email").focus();
}

async function showAccount() {
  const user = await api("/me", { headers: { Authorization: `Bearer ${token}` } });
  $("loading-view").hidden = true;
  $("auth-view").hidden = true;
  $("account-view").hidden = false;
  $("retry-button").hidden = true;
  $("step-label").textContent = "SYSTEM / PLAYER CONNECTED";
  $("account-email").textContent = user.email;
  $("account-role").textContent = user.role === "admin" ? "★ ADMINISTRATOR" : "↳ UŻYTKOWNIK";
  $("password").value = "";
  $("confirm-password").value = "";
  document.title = "Twoje studio — AI-Slop";
  history.replaceState(null, "", "/app");
  showMessage("");
  clearTimeout(expiryTimer);
  // The API validates the signature; this timestamp only controls the UI timer.
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    expiryTimer = setTimeout(() => {
      saveToken(null);
      firstAccount = false;
      setMode("login");
      showMessage("Sesja wygasła. Zaloguj się ponownie.");
    }, Math.max(0, payload.exp * 1000 - Date.now()));
  } catch { /* API remains the authority on token validity. */ }
}

async function initialize() {
  $("retry-button").hidden = true;
  $("loading-view").hidden = false;
  $("auth-view").hidden = true;
  $("account-view").hidden = true;
  showMessage("");
  try {
    if (!apiBaseUrl) {
      const response = await fetch("/config", { cache: "no-store", signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error("Nie udało się wczytać konfiguracji studia.");
      const config = await response.json();
      apiBaseUrl = config.api_base_url;
    }
    const status = await api("/setup");
    firstAccount = status.registration_required;
    if (token && !firstAccount) {
      try { await showAccount(); return; }
      catch (error) { if (error.status !== 401) throw error; saveToken(null); }
    }
    if (firstAccount) saveToken(null);
    setMode(firstAccount || location.pathname === "/register" ? "register" : "login", true);
  } catch (error) {
    $("loading-view").hidden = true;
    showMessage(error.message);
    $("retry-button").hidden = false;
  }
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  if (mode === "register" && $("password").value !== $("confirm-password").value) {
    showMessage("Hasła nie są takie same. Wpisz je ponownie.");
    $("confirm-password").focus();
    return;
  }
  const credentials = { email: $("email").value.trim(), password: $("password").value };
  busy = true;
  $("form-fields").disabled = true;
  $("auth-form").setAttribute("aria-busy", "true");
  $("submit-label").textContent = "CHWILKA…";
  showMessage("");
  try {
    if (mode === "register") {
      await api("/register", { method: "POST", body: JSON.stringify(credentials) });
      firstAccount = false;
      setMode("login");
      showMessage("Konto utworzone! Zaloguj się, aby wejść do studia.", true);
    } else {
      const result = await api("/login", { method: "POST", body: JSON.stringify(credentials) });
      saveToken(result.access_token);
      await showAccount();
    }
  } catch (error) {
    showMessage(error.message);
    if (error.status === 409) {
      firstAccount = false;
      $("setup-note").hidden = true;
      $("switch-line").hidden = false;
    }
  } finally {
    busy = false;
    $("form-fields").disabled = false;
    $("auth-form").removeAttribute("aria-busy");
    $("submit-label").textContent = mode === "register" ? "UTWÓRZ KONTO" : "WEJDŹ DO STUDIA";
  }
});

$("switch-link").addEventListener("click", (event) => {
  event.preventDefault();
  if (!busy) setMode(mode === "login" ? "register" : "login");
});
$("toggle-password").addEventListener("click", () => {
  const visible = $("password").type === "password";
  $("password").type = visible ? "text" : "password";
  $("toggle-password").textContent = visible ? "UKRYJ" : "POKAŻ";
  $("toggle-password").setAttribute("aria-pressed", String(visible));
  $("toggle-password").setAttribute("aria-label", visible ? "Ukryj hasło" : "Pokaż hasło");
});
$("logout-button").addEventListener("click", () => {
  clearTimeout(expiryTimer);
  saveToken(null);
  firstAccount = false;
  setMode("login");
  showMessage("Wylogowano ze studia.", true);
});
$("retry-button").addEventListener("click", initialize);
initialize();
