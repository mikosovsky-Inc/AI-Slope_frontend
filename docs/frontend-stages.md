# Stan i etapy frontendu

## Analiza kontraktu — 2026-10-01

Źródłem prawdy są app/api/router.py, zarejestrowane routes, schematy oraz testy
backendu. Historyczne zdania „kolejny etap nie został rozpoczęty” w architecture.md
są zapisami dawnych etapów, nie opisem aktualnych możliwości.

### Current backend capabilities

Auth: POST /api/v1/auth/register i /login, GET /auth/setup i /auth/me.
Credentials zawierają email/password, rejestracja wymaga 12–128 znaków hasła.
Login zwraca access_token, token_type=bearer, expires_in. Setup zwraca
registration_required. Me zwraca id, email, role, is_active, created_at.
Backend ustala role i weryfikuje JWT oraz aktywność użytkownika.

Istnieją API kanałów, blueprintów, analizy, konkurentów, pomysłów, scenariuszy,
researchu, reżyserii, generowania zasobów/audio, renderowania, jakości, kosztów,
dashboardu, scen, zadań, rewizji i odzyskiwania zadań. Scheduler działa po stronie
backendu; sama obecność pustych plików routes/publications.py czy schedules.py
nie oznacza zarejestrowanych endpointów. Publikacji do platform jeszcze nie ma.

Kanały: draft/active/paused. Autopilot: manual/semi_auto. Zadania:
queued/running/succeeded/failed/needs_review. Statusy Video są wielkimi literami,
np. SCRIPT_READY, GENERATING_ASSETS, READY, FAILED. Frontend nie definiuje własnej
maszyny stanów ani automatycznych przejść.

### Current frontend state

Przed zmianą: statyczny ekran auth, sessionStorage, bezpośrednie wywołania API
z przeglądarki. Puste moduły stron nie były zaimplementowanymi funkcjami.
Po etapie 1: Jinja2 SSR, BackendClient, ciasteczko HttpOnly, CSRF, formularze
bez JS, pixelowy CSS zachowany. Nie dodano fikcyjnych statystyk ani akcji domenowych.

### Contract mismatches

Usunięto publiczne /config i połączenia browser → backend; API_BASE_URL stało się
adresem serwerowym. Zastąpiono JWT w sessionStorage ciasteczkiem. Dokumentacja
wcześniej wskazywała nieistniejący run.sh; aktualna instrukcja podaje uv --no-active.
Stary backendowy browser_smoke.py używa selektorów i architektury wcześniejszej
wersji: aktualny test przeglądarkowy jest w repozytorium frontendu.

### Next implementation step

1. [x] Fundament SSR, BackendClient, auth, błędy, testy.
2. [x] Dashboard i lista kanałów z rzeczywistych endpointów.
3. [x] Onboarding kanału i setup/strategy, polling analizy.
4. [ ] Konkurenci i pomysły.
5. [ ] Filmy, sceny, produkcja i podgląd zasobów.
6. [ ] Koszty, zadania, odzyskiwanie, dostępność i integracja całego workflow.

Załączona specyfikacja odwołuje się do niewklejonej wcześniejszej części.
Powyższa kolejność wynika z istniejącego kodu; nie przypisuje historycznych numerów
nieznanemu planowi. W tym kroku zaimplementowano wyłącznie pierwszy brakujący fundament.

## Walidacja

14 testów deterministycznych (mock HTTP); Ruff. Lokalny backend :8000 i Docker
były niedostępne. Smoke używa prawdziwego backendu w oddzielnym procesie HTTP,
z izolowanym SQLite w pamięci i mock providerami. To test auth, nie migracji ani
blokady pierwszego administratora w PostgreSQL; te sprawdzają testy backendowe.

Wynik smoke: PASS — konta admin/user, pełny auth, odświeżenie, logout, JS on/off,
brak przewijania poziomego na 390 px. Obejrzano zrzuty desktop/mobile.
OpenAPI uruchomionego backendu: 52 ścieżki, cztery endpointy auth zgodne z klientem.
14 testów przeszło; dwa ostrzeżenia deprecacji pochodzą z bibliotek TestClient/AnyIO.


## Etap 2 — dashboard i lista kanałów (zakończony)

Przed implementacją sprawdzono routes/channels.py, routes/panel.py, serwis panelu,
schematy ChannelPage/Dashboard, testy test_panel.py i test_channels.py oraz
OpenAPI działającego backendu. Brak rozbieżności kontraktu w zakresie etapu.

- `/app`: dashboard z GET /api/v1/dashboard: liczniki kanałów/filmów, statusy,
  do 10 ostatnich filmów i koszty całej historii (nie miesięczne).
- `/channels`: GET /api/v1/channels?limit=12&offset=…; paginacja po stronie API.
- Obie strony weryfikują sesję przez /auth/me i przekazują JWT tylko backendowi.
  401 usuwa sesję i przekierowuje do logowania; awaria pozostawia ciasteczko.
- Walidacja projekcji odpowiedzi przez Pydantic; brak kopii enumów domenowych.
  Nieznany status jest wyświetlany jako wartość backendowa, nie gubi danych.
- Koszt łączny to effective_usd: koszt rzeczywisty lub szacunek, gdy rzeczywistego
  brak. UI informuje o liczbie oczekujących rozliczeń. Nie sumuje kosztów samodzielnie.
- Puste dane, strona poza zakresem i błędy 403/503 mają osobne widoki.
- Pixelowy układ responsywny, nawigacja, skip-link, bezpieczne escapowanie tekstu.
- Odczyt danych bez JavaScript; odświeżanie ręczne. Polling będzie częścią
  obsługi zadań, nie dodano zbędnego cyklicznego odpytywania tych ekranów.

Walidacja: 25 testów jednostkowych, Ruff i diff-check. Smoke prawdziwego backendu
na izolowanej bazie SQLite: 13 kanałów, strony 12+1, dashboard, nawigacja,
wylogowanie, Chromium i WebKit, brak overflow na 390 px. Obejrzano zrzuty ekranów.
Backend produkcyjny i jego dane nie były modyfikowane.
Następny etap: onboarding kanału i konfiguracja/strategia wraz z pollingiem analizy.


## Etap 3 — onboarding, ustawienia i analiza kanału (zakończony)

Przeczytano aktualne ChannelCreate/Update/Detail, TaskRead, serwisy kanałów,
intelligence, enqueue/read_task oraz testy channels/intelligence/tasks.
Backend na :8000 nie działał podczas tego etapu; użyto OpenAPI prawdziwego,
izolowanego backendu :18091. Frontend nadal komunikuje się wyłącznie przez HTTP.

Dodano /channels/new i /channels/{id}: utworzenie z opisu (nazwa opcjonalna),
język, częstotliwość, budżet i tryb pracy. Zapis ustawień wysyła tylko te pola;
nie zastępuje blueprintu ani filarów tematycznych. Języki i tryby pochodzą
z OpenAPI. Nie dodano własnych domenowych enumów ani parsowania opisu na ustawienia.
Błędy zapisu zachowują wpisane wartości. Formularze działają bez JS.

Strategia jest podglądem wyniku analizy: nisza, odbiorcy, ton, hook, formaty,
długość/tempo, styl wizualny, słowa kluczowe, sugerowany rytm i filary.
Ręczny edytor pełnego blueprintu nie jest częścią tego etapu. Analiza zastępuje
strategię, ale nie stosuje sugerowanej częstotliwości do ustawień kanału.
Przyciski aktywacji/wstrzymania wywołują odpowiednie endpointy backendu.

Analiza obsługuje odpowiedź synchroniczną ChannelDetail oraz asynchroniczną
TaskRead. POST używa Idempotency-Key z formularza (ponowienie tej samej próby
zachowuje klucz). To nie oznacza globalnej deduplikacji analiz otwartych w różnych
kartach. Utworzenie kanału nie ma backendowej idempotencji, dlatego błędy sieci
nie powodują automatycznego ponowienia POST.

URL szczegółów zawiera task_id z odpowiedzi backendu; polling GET przez frontend
co 5 sekund, bez nakładania żądań, pauza w niewidocznej karcie, limit 120 odczytów.
Sukces/błąd kończy polling i odświeża widok. 401 prowadzi do logowania;
błąd sieci kończy automatyczne odświeżanie z czytelnym komunikatem.
Bez JS dostępne jest ręczne odświeżenie. Luka w historii zadań jest opisana
w backend-requirements.md. Status zadania jest prezentowany bez procentów postępu,
których API nie dostarcza.

Walidacja: 41 testów, Ruff, diff-check. Chromium i WebKit: tworzenie kanału,
zapis częstotliwości, zadanie analizy wykonane przez prawdziwy runner z mock LLM,
podgląd strategii, zachowanie ustawień, activate/pause, brak overflow przy 390 px.
Test korzysta z izolowanej bazy SQLite; testowy mechanizm uruchamia runner przy
odczycie zadania — nie sprawdza dostarczania z Redis/Dramatiq. Obejrzano zrzuty.
Następny etap: konkurenci i pomysły.

Test bez JS wykrył wyścig między odczytem kanału a końcem zadania.
Poprawiono kolejność odczytów: status zadania, potem strategia. Dodano regresję.
