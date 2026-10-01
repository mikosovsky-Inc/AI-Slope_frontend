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
4. [x] Konkurenci i pomysły.
5. [x] Filmy, sceny, produkcja i podgląd zasobów.
6. [x] Koszty, zadania, odzyskiwanie, dostępność i integracja całego workflow.
7. [x] Podsumowanie kanału i podgląd ostatniego planu produkcji.
8. [x] Historia kontroli jakości filmu.

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


## Etap 4 — konkurenci i pomysły (zakończony)

Przed implementacją sprawdzono routes/ideas.py i channels.py, schematy
CompetitorResearchResult/CompetitorPage/ResearchSummary, IdeaPage/IdeaRead/IdeaBatch,
serwisy decide_idea/generate_ideas, lokalny research provider oraz testy ideas
 i competitors. OpenAPI potwierdzono na izolowanym uruchomionym backendzie.

Dodano zakładki /channels/{id}/competitors i /channels/{id}/ideas, osiągalne ze
szczegółów kanału. Listy mają paginację po 10. Pomysły można filtrować według
statusów pobranych z OpenAPI. Formularz generowania przesyła count jako query
param (10–20), nie jako JSON body. Badanie konkurentów wywołuje
/channels/{id}/competitor-research. Obie operacje mają Idempotency-Key oraz
obsługują wyniki synchroniczne i TaskRead. Stan zadania czytany jest przed wynikami.

Pomysły pokazują koncept, filar, format, hook, uzasadnienie oraz heurystyki
z objaśnieniami. Approve/reject są formularzami POST z CSRF, przekazanymi do API.
Backend decyduje o dozwolonych zmianach; used nie pokazuje przycisków decyzji.
Po decyzji filtr i offset pozostają zachowane; kanał przekierowania pochodzi
z odpowiedzi API. Pusta strona po decyzji pozwala wrócić na pierwszą stronę.
Tworzenie Video zostaje w etapie 5, wraz z widokiem filmu.

Konkurenci to lokalne benchmarki skonfigurowanego providera. UI nie obiecuje
wyszukiwania internetu, wyświetla brak danych zamiast zerowych metryk. Pusty
research nie usuwa poprzednich rekordów. Linki do profili są walidowane jako
AnyHttpUrl, otwierane z noopener/noreferrer; tekst jest escapowany przez Jinja2.
Odpowiedzi list są walidowane przez modele Pydantic. Brakujące funkcje domenowe
nie zostały dodane do frontendu ani backendu.

Walidacja: 61 testów jednostkowych, Ruff, diff-check. Integration smoke na
prawdziwym backendzie z mock LLM i izolowanym SQLite: 12 pomysłów, strony 10+2,
approve/reject, filtry, zakończony research z pustym lokalnym źródłem. Chromium
z pollingiem oraz WebKit bez JS; ręcznie obejrzane screenshoty desktop/mobile.
Testowy runner jest uruchamiany przy odczycie zadania w izolowanym harnessie;
test nie pokrywa dostarczania Redis/Dramatiq ani płatnych providerów.

Następny etap: filmy, sceny, produkcja i podgląd zasobów.


## Etap 5 — filmy, sceny, produkcja i zasoby (zakończony)

Sprawdzono routes ideas/panel/render/scripts/research, VideoRead/SceneRead/StatusRead,
AssetRead, serwisy create_video/start_production/edit_scene/regenerate oraz
kontynuację workflow w workerze. OpenAPI potwierdzono na uruchomionym backendzie
testowym. Backend jest źródłem statusów, walidacji i dozwolonych przejść.

### Funkcje

- Pomysł approved: POST create-video, przekierowanie na film. Used: ta sama
  idempotentna operacja otwiera istniejący film. Obsługiwane odpowiedzi 200/201/202.
- Utworzenie w trybie asynchronicznym może uruchomić cały pipeline do jakości,
  nie tylko scenariusz. Frontend nie wysyła równolegle dodatkowego produce.
- /channels/{id}/videos: lista po 10, filtrowanie statusami z OpenAPI.
  Linki z kanału, pomysłów i ostatnich filmów dashboardu.
- /videos/{id}: szczegóły, aktualny stan, ostatnie zadania (limit API 100), sceny,
  zasoby; odświeżanie przez /video-status/{id}. Backendowy has_active_tasks
  steruje pollingiem. Zmiana stanu odświeża stronę; niezapisane pola blokują
  automatyczny reload. Wtedy UI informuje o nowych danych. Ręczny refresh działa bez JS.
- Przy idle SCRIPT_READY można zlecić produkcję. W trybie eager lub bez
  rozpoczętego workflow dostępne są odpowiednie akcje przygotowania STORY,
  research TOP5 i scenariusza TOP5. Końcowe uprawnienia/stany sprawdza backend.
- Edytor scen: narracja STORY, visual_prompt, mood, caption_emphasis (wiersze).
  TOP5 nie wysyła narracji nawet po ręcznej manipulacji formularzem. Backend
  blokuje sceny z historią generacji i aktywne zadania. Błąd zachowuje wpisane pola.
- Regeneracja obrazu/wideo zgodnie z visual_type oraz audio, z Idempotency-Key.
  Regeneracja sceny nie jest obietnicą przebudowania gotowego filmu; rewizje i
  odzyskiwanie pozostają etapem 6. Niedozwolone operacje dostają komunikat 409.

### Media

/media/{asset_id} weryfikuje dostęp przez pobranie pliku z backendu z JWT użytkownika.
Nie otwiera lokalnego storage backendu ani bucketa. JWT nie trafia do HTML, URL
ani JavaScript. Backend nadal sprawdza własność i integralność pliku.

Plik jest pobierany strumieniowo do prywatnego pliku tymczasowego, następnie
FileResponse obsługuje Range/206 (potrzebne m.in. WebKit). Usuwanie w finally
obejmuje również błędny zakres i rozłączenie klienta. Bez współdzielonego cache,
bez publicznych ścieżek. Domyślny limit MEDIA_MAX_BYTES: 512 MiB na pobranie.
Przy każdym żądaniu zakresu frontend pobiera cały plik z backendu — to koszt
obecnego braku Range w API, a nie optymalny transport dużych plików.

Inline dopuszczone wyłącznie typy rastrowych obrazów, MP4/WebM i audio.
Pozostałe typy, w tym napisy, są pobierane jako application/octet-stream attachment.
Nazwy plików oparte są o UUID, nie o niezweryfikowany nagłówek backendu.
Wideo/audio mają preload=none, obrazy lazy. Brak automatycznej publikacji.

### Walidacja

76 testów jednostkowych, Ruff, format-check i diff-check. Testy obejmują
create-video bez podwójnego uruchamiania, paginację, aktywne zadania, TOP5,
zachowanie edycji po błędzie, CSRF, zgodność sceny z filmem, klucze regeneracji,
auth mediów, Range 206/416, bezpieczne MIME, limit rozmiaru i cleanup.

Integracja: prawdziwy backend HTTP + tymczasowy SQLite/storage + mock providerzy,
runnery zadań wykonane w tle, FFmpeg. Film STORY 45 s przeszedł cały pipeline do
READY. Chromium i WebKit faktycznie odtworzyły final_video (currentTime > 0),
pobrały Range 0–31 (206), bez overflow przy 390 px. Obejrzano screenshot WebKit.
Nie testowano Redis/Dramatiq ani płatnych providerów. Wstępny 10-sekundowy fixture
miał sceny krótsze od części mock narracji i został poprawnie zablokowany przez
renderer; zmieniono dane testowe, nie reguły backendu.

Następny etap: szczegóły kosztów, obsługa zadań i odzyskiwanie/rewizje.

## Etap 6 — koszty, zadania i rewizje (zakończony)

Sprawdzono kontrakty panelu, admin/jobs, task recovery i revisions oraz ich
ograniczenia w serwisach backendu. Dodano projekcje Pydantic i strony SSR:

- koszty kanału (20 zdarzeń/stronę), szacunek vs rozliczenie, suma całej historii;
- budżet filmu bez lokalnego przeliczania;
- szczegóły zadania, retry, resume/use_asset/abandon i historia odzyskiwania;
- administracyjna lista zadań z filtrami i licznikami przed filtrem statusu;
- rewizje: szkic, edycja scen, produkcja, anulowanie, pobranie starszej wersji.

Brak filtra statusu jobs oznacza aktywne i wymagające uwagi, zgodnie z API.
Admin widzi metadane innych użytkowników; szczegóły i operacje są owner-scoped.
JWT pozostaje w HttpOnly, wszystkie mutacje wymagają CSRF. Formularze działają
bez JS. Potwierdzenia porzucenia/anulowania są sprawdzane także serwerowo.
Narracja TOP5 nie trafia do PATCH nawet po manipulacji formularzem.
Backend pozostaje odpowiedzialny za limity retry, walidację zasobów, wznowienie
checkpointów, stan filmu i możliwość anulowania aktywnej produkcji.

Zadania queued/running używają istniejącego pollingu. Rewizje mają ręczne
odświeżenie i link do śledzenia produkcji filmu; brak automatycznego przeładowania
chroni niezapisane formularze scen. Pole provider_job_id służy wyłącznie do
oryginalnego identyfikatora zadania, nie sekretów. Nie pokazujemy surowych
wyników zadań ani wewnętrznych dowodów providera.

Walidacja: 92 testy, Ruff, format-check i diff-check. Mock HTTP obejmuje
mapowanie retry i trzech metod odzyskiwania, CSRF, wymagane potwierdzenie,
zachowanie błędnej edycji, narrację TOP5, obcą scenę, auth i rolę administratora.
Smoke prawdziwego backendu z izolowanym SQLite/storage, mock providerami i FFmpeg:
Chromium/WebKit, koszty, budżet, puste opcjonalne filtry jobs, szczegóły zadania;
utworzenie rewizji, zmiana ruchu kamery, produkcja wersji 2 do ready,
zachowanie wersji 1, anulowanie szkicu wersji 3. Odtwarzanie i Range nadal działają.
Obejrzano screenshot mobilny WebKit; brak overflow przy 390 px.
Odzyskiwanie niepewnych zadań sprawdzono przez mock HTTP, nie przez żywego
płatnego providera. Smoke nie sprawdza Redis/Dramatiq ani PostgreSQL.

## Etap 7 — podsumowanie kanału i plan produkcji (zakończony)

Po ukończeniu sześciu etapów podstawowych uzupełniono istniejący, dotąd niewykorzystany
GET /api/v1/channels/{id}/overview. Sprawdzono schemas Overview/PlanRead,
service.overview, scheduler/service.py i testy panelu dotyczące auth oraz własności.

Nowy /channels/{id}/overview jest dostępny z ustawień kanału. Pokazuje konfigurację,
liczniki pomysłów i filmów z linkami do filtrowanych list, koszty całej historii
oraz ostatni zapisany plan: dzień, status, cel i powód blokady. Znane stany i powody
mają polskie opisy; nieznane wartości pozostają widoczne. waiting_approval prowadzi
do kandydatów. complete oznacza ukończenie planowania, nie render ani publikację.
Data planu jest pokazywana bez założenia, że dotyczy dzisiejszego dnia.

Frontend używa wyłącznie API, waliduje odpowiedź przez Pydantic. Ekran jest
SSR, działa bez JS i ma ręczne odświeżenie. Nie dopisano lokalnego schedulera,
kalendarza ani przycisków mutacji, dla których brak kontraktu API.

Walidacja: 102 testy, Ruff i format-check. Nowe regresje obejmują pusty plan,
statusy znane/nieznane, starszy dzień, escapowanie tekstu, kodowanie filtrów,
401/403/404/503 i niepoprawną odpowiedź backendu. Smoke przeciw prawdziwemu API
na izolowanym SQLite potwierdził OpenAPI, nawigację, pusty plan i koszty w Chromium
oraz WebKit z wyłączonym JS. Obejrzano screenshot mobilny, brak overflow 390 px.
Smoke nie uruchamia schedulera ani nie sprawdza jego dostarczania zadań;
niepuste plany sprawdzono deterministycznie z mock HTTP.

## Etap 8 — historia kontroli jakości (zakończony)

Ponownie przesłana specyfikacja zachowuje dotychczasowy kierunek. Audyt
zarejestrowanych routes wykazał niewykorzystany przez frontend GET quality-checks.
Sprawdzono routes/quality.py, QualityCheckRead/QualityReport, statusy QualityStatus,
read_checks, testy quality (auth, własność, skipped, naprawy) i historię etapu 16.

Dodano /videos/{id}/quality, dostępny z filmu. Projekcje Pydantic obejmują raport,
kontrole, identyfikatory powiązań i daty. Pusty report_json podczas sprawdzania
jest poprawnym stanem. Wyniki nieznane pozostają widoczne. Interfejs rozróżnia
passed/failed/skipped; repaired nie oznacza gotowego filmu. Starszy raport
nie jest interpretowany jako kontrola aktualnego renderu. Link pobrania używa
final_asset_id konkretnego raportu. Kod nie pokazuje surowych danych providera.

Odczyt przez BackendClient z sesją właściciela; brak lokalnej logiki oceny,
bez dostępu do ORM/storage. Ekran jest SSR, z ręcznym odświeżaniem. W tym etapie
nie dodano ręcznego wywoływania QC — produkcja już zleca kontrolę automatycznie.
Nie ma blokujących braków kontraktu dla historii raportów.

Walidacja: 109 testów, Ruff, format-check, diff-check. Nowe testy pokrywają
pustą historię i raport w toku, skipped/failed/nieznane wyniki, escapowanie,
zerową długość, dokładny final_asset_id, auth, błędy API i walidację odpowiedzi.
Smoke: prawdziwy backend HTTP z izolowanym SQLite/storage, mock providerzy,
FFmpeg; film READY, odtwarzanie i Range, raport passed oraz skipped dla disabled
visual provider w Chromium/WebKit. Obejrzano mobilny screenshot WebKit;
brak overflow przy 390 px. Nie testowano płatnego vision ani Redis/Dramatiq.
