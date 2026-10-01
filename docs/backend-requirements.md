# Braki kontraktu backendu

## Etap 1: SSR / auth

Brak blokujących braków. Istniejące setup/register/login/me wystarczają.
Wylogowanie usuwa ciasteczko; nie obiecujemy unieważnienia JWT po stronie API.

## Publikacja na TikTok / YouTube — poza bieżącym etapem

Nie ma zarejestrowanego API podłączenia kont i publikowania. Nie pokazujemy
przycisku publikacji jako działającego. Poniżej propozycja do uzgodnienia
przed etapem publikacji, nie istniejący kontrakt:

- POST /api/v1/channels/{channel_id}/platform-connections: request platform;
  response authorization_url, expires_at. UX: rozpoczęcie połączenia konta.
- GET /api/v1/channels/{channel_id}/platform-connections: bez body;
  response items z id, platform, display_name, status. UX: stan połączenia.
- POST /api/v1/videos/{video_id}/publications: request connection_id,
  scheduled_at (opcjonalnie); response id, status, scheduled_at.
  UX: zlecenie publikacji gotowego filmu.
- GET /api/v1/videos/{video_id}/publications: bez body; response items z id,
  platform, status, published_at, external_url, error_code.
  UX: potwierdzenie wyniku bez udawania sukcesu.

Backend musi ustalić OAuth callback, walidację, idempotencję i dozwolone statusy.
Frontend nie będzie przechowywać tokenów platform ani wykonywać tej logiki.


## Etap 2: dashboard i lista kanałów

Brak blokujących braków: GET /api/v1/dashboard i GET /api/v1/channels obsługują
podsumowanie i paginację. Nie dodano filtrowania kanałów ani statystyk miesięcznych,
ponieważ te endpointy ich nie udostępniają. W tym etapie nie są wymagane.


## Etap 3: wznowienie śledzenia analizy po opuszczeniu strony

Brak listy zadań kanału. Obecny GET /api/v1/tasks/{task_id} działa, kiedy frontend
zna task_id otrzymany przy zleceniu. Frontend zachowuje go w URL. Po wejściu na
kanał z listy nie odtwarza bieżącej analizy ani historii. TaskRead nie zawiera
channel_id, więc sam odczyt zadania potwierdza właściciela, ale nie powiązanie
z aktualnie oglądanym kanałem. Nie udajemy globalnej blokady równoległej analizy.

Minimalna propozycja:
- GET /api/v1/channels/{channel_id}/tasks
- Request: query kind (opcjonalny), limit, offset; bez body.
- Response: items (TaskRead uzupełniony o channel_id), total, limit, offset.
- UX: odtworzenie aktywnej analizy po powrocie i pokazanie jej historii.
- Backend: własność kanału, filtr i stabilne sortowanie po created_at/id.

To propozycja API, nie zaimplementowany endpoint. Bezpośredni dostęp do DB
lub odgadywanie task_id nie jest rozwiązaniem używanym przez frontend.
