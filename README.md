# AI-Slop frontend

Osobna aplikacja FastAPI + Jinja2, HTML, CSS i plain JavaScript w pixelowym stylu.
Przeglądarka komunikuje się wyłącznie z frontendem. `BackendClient` wywołuje API
backendu po HTTP. Brak importów backendu, połączenia z bazą i kopii logiki domenowej.

## Uruchomienie

```sh
uv sync --no-active
cp .env.example .env
uv run --no-active uvicorn main:app --reload --port 3000
```

Otwórz http://localhost:3000. `API_BASE_URL` to adres backendu dostępny **z serwera
frontendu**, domyślnie http://localhost:8000. W sieci Compose może to być
http://api:8000. Przeglądarka nie potrzebuje dostępu do tego adresu ani CORS.
Przy HTTPS ustaw `COOKIE_SECURE=true`. Frontend nie potrzebuje sekretu JWT.

## Etap 1 — fundament SSR i uwierzytelnianie

Zakończony: formularze Jinja2, BackendClient, rejestracja, logowanie, odczyt konta,
wylogowanie, błędy API i niedostępność serwera. Działają bez JavaScript; JS dodaje
przełączanie widoczności hasła i usuwa token pozostały po poprzedniej wersji.

Pusta baza wyświetla rejestrację. Istniejące konta — logowanie. O roli pierwszego
administratora decyduje backend. JWT jest w ciasteczku HttpOnly/SameSite=Lax,
z czasem życia otrzymanym od backendu. Każdy odczyt konta weryfikuje sesję przez
`/api/v1/auth/me`. Formularze POST wymagają tokenu CSRF. Odpowiedzi nie są cache’owane.
Wylogowanie usuwa ciasteczko; backend nie unieważnia wystawionego JWT.
Nie ma magazynu sesji w pamięci procesu ani wymogu wspólnego procesu z backendem.

## Testy

```sh
uv run --no-active pytest
uv run --no-active ruff check .
uv run --no-active ruff format --check .
```

Testy jednostkowe używają `httpx.MockTransport`; nie wymagają providerów ani bazy.
Test przeglądarkowy tworzy dwa konta, więc uruchamiaj go **wyłącznie przeciwko
izolowanemu, pustemu backendowi testowemu**, z mock providerami. Frontend musi
wskazywać ten backend przez `API_BASE_URL`:

```sh
uv run --no-active playwright install chromium
uv run --no-active python tests/browser_smoke.py --isolated-frontend-url http://localhost:3000
```

Sprawdza role admin/user, rejestrację, logowanie, odświeżenie, wylogowanie,
JS włączony/wyłączony i szerokość mobilną. Zrzuty zapisuje w `/tmp/ai-slop-ssr-*.png`.
Stary `tests/browser_smoke.py` w backendzie dotyczy poprzedniego frontendu SPA.

Plan i analiza: [docs/frontend-stages.md](docs/frontend-stages.md).
Braki API: [docs/backend-requirements.md](docs/backend-requirements.md).


## Etap 2 — Studio i Kanały

Po zalogowaniu `/app` pokazuje liczniki, koszty całej historii, statusy i ostatnie
filmy. `/channels` prezentuje kanały po 12 na stronę. Obie strony pobierają dane
użytkownika z backendu; są dostępne bez JavaScript. Tworzenie i konfiguracja kanału
należą do kolejnego etapu. Aktualnie nie ma przycisków do tych operacji.

Dodatkowy test integracyjny tworzy 13 kanałów w **izolowanym** backendzie:

```sh
uv run --no-active playwright install chromium webkit
uv run --no-active python tests/panel_smoke.py \
  --isolated-frontend-url http://localhost:13001 \
  --isolated-backend-url http://localhost:18091
```

Frontend testowy musi wskazywać ten sam backend. Test sprawdza paginację,
dashboard, mobilny układ i wylogowanie w Chromium oraz WebKit (bez JavaScript).
