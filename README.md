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
użytkownika z backendu; są dostępne bez JavaScript. Tworzenie i konfiguracja kanału są dostępne od etapu 3.

Dodatkowy test integracyjny tworzy 13 kanałów w **izolowanym** backendzie:

```sh
uv run --no-active playwright install chromium webkit
uv run --no-active python tests/panel_smoke.py \
  --isolated-frontend-url http://localhost:13001 \
  --isolated-backend-url http://localhost:18091
```

Frontend testowy musi wskazywać ten sam backend. Test sprawdza paginację,
dashboard, mobilny układ i wylogowanie w Chromium oraz WebKit (bez JavaScript).


## Etap 3 — utworzenie kanału i strategia

Kliknij **Utwórz kanał**, wpisz opis i język. Nazwa jest opcjonalna; backend nada
ją z opisu. Częstotliwość, budżet i tryb pracy są pod rozwijanymi ustawieniami.
Po zapisie otwórz **Analizuj opis kanału**. Wynik obejmuje m.in. odbiorców,
formaty i filary tematyczne. Ponowna analiza zastępuje strategię.

Analiza asynchroniczna wymaga działających backendowych workerów. Frontend
odświeża jej stan; bez JavaScript użyj **Odśwież stan**. Zachowaj URL z task_id,
żeby wrócić do śledzenia tej próby. W razie błędu automatyczny polling zatrzymuje się.
Języki i tryby pracy pobierane są z /openapi.json backendu, który musi być dostępny
z serwera frontendu. Przy mock LLM strategia jest przykładową odpowiedzią backendu.

Test przeglądarkowy (wyłącznie izolowany stack, mock provider i działający worker):

```sh
uv run --no-active python tests/channel_smoke.py \
  --isolated-frontend-url http://localhost:13001 \
  --isolated-backend-url http://localhost:18091
```

Sprawdza Chromium z pollingiem i WebKit bez JS z ręcznym odświeżeniem.


## Etap 4 — konkurenci i pomysły

W szczegółach kanału wybierz **Konkurenci** lub **Pomysły**. Po przygotowaniu
strategii możesz zlecić badanie lokalnych benchmarków albo wygenerować 10–20
pomysłów. Listy mają paginację. Pomysły można filtrować, zatwierdzać i odrzucać;
wykorzystanych pomysłów nie można zmieniać. Utworzenie filmu jest dostępne od etapu 5.

Badanie konkurencji obecnie korzysta z rekordów providera backendowego, nie
przeszukuje internetu. Brak wyników jest prawidłowy przy pustej konfiguracji.
Heurystyki pomysłów nie są prognozami wyświetleń. Zadania obsługują polling
oraz ręczne odświeżanie bez JS. Zachowaj adres z task_id do śledzenia danej próby.

Test integracyjny (izolowany stack, mock LLM, worker):

```sh
uv run --no-active python tests/editorial_smoke.py \
  --isolated-frontend-url http://localhost:13001 \
  --isolated-backend-url http://localhost:18091
```

Test tworzy syntetyczne konta i treści — nie uruchamiaj go na swoich danych.


## Etap 5 — filmy, sceny i produkcja

Na zatwierdzonym pomyśle kliknij **Utwórz film**. W trybie asynchronicznym backend
może uruchomić cały pipeline, łącznie z generowaniem zasobów i renderem.
**Otwórz film** na wykorzystanym pomyśle prowadzi do istniejącego filmu.
W zakładce **Filmy** znajdziesz listę i filtr statusów.

Szczegóły filmu pokazują zadania, sceny i zasoby. Przy aktywnych zadaniach stan
odświeża się automatycznie; niezapisane zmiany w formularzu blokują reload.
**Uruchom produkcję** jest dostępne dla gotowego scenariusza bez aktywnych zadań.
Edycja scen i pojedyncze generacje podlegają ograniczeniom backendu. Narracji
TOP5 nie można edytować niezależnie od researchu. Obsługa rewizji i odzyskiwania
będzie częścią kolejnego etapu.

Podgląd/pobieranie zasobów odbywa się przez uwierzytelniony frontend. Wymaga
wolnego miejsca w katalogu plików tymczasowych: do `MEDIA_MAX_BYTES` na pobranie
(domyślnie 536870912 bajtów). Pliki są usuwane po odpowiedzi. Obsługiwany jest
Range, ale każde żądanie pobiera cały zasób z backendu — większe pliki będą
wymagać optymalizacji kontraktu API opisanej w backend-requirements.md.

Test prawdziwej produkcji i odtwarzania, **wyłącznie izolowany mock stack**:

```sh
uv run --no-active python tests/video_smoke.py \
  --isolated-frontend-url http://localhost:13001 \
  --isolated-backend-url http://localhost:18091
```

Wymaga FFmpeg/FFprobe i działającego workera. Tworzy testowy film STORY;
sprawdza READY, odtwarzanie Chromium/WebKit i pobieranie zakresowe.
