# AI-Slop frontend

Samodzielny frontend HTML, CSS i plain JavaScript w pixelowym stylu,
hostowany przez własny serwer FastAPI. Bez Node.js i budowania assetów.
Nie importuje backendu i nie łączy się bezpośrednio z bazą danych.

## Uruchomienie

W katalogu `AI-Slop_frontend`:

```sh
env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=.venv uv sync
cp .env.example .env
./run.sh
```

Otwórz http://localhost:3000/.
`run.sh` zawsze wskazuje `.venv` tego projektu i usuwa odziedziczone `VIRTUAL_ENV`
tylko dla uruchamianego procesu. Skrypt uruchamiaj bezpośrednio jako `./run.sh`,
nie przez zewnętrzne `uv run ./run.sh`. Działa również z aktywnym środowiskiem backendu
oraz po wywołaniu skryptu z innego katalogu. Dodatkowe argumenty przekazuje do
Uvicorn, np. `./run.sh --port 3001`.

Przy ręcznym uruchamianiu możesz najpierw wykonać `deactivate` w terminalu
z aktywnym środowiskiem backendu. Ostrzeżenie uv o niedopasowanym `VIRTUAL_ENV`
oznaczało, że ignorował to środowisko i wybierał projektowe `.venv`.
Nie używaj `--active`, jeśli aktywne jest środowisko innego projektu.
[Zasady wyboru środowiska uv](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path).

W osobnym terminalu uruchom skonfigurowany backend:

```sh
# W katalogu AI-Slop_backend
uv run uvicorn main:app --reload --port 8000
```

`API_BASE_URL` w `.env` frontendu wskazuje publiczny adres backendu, domyślnie
`http://localhost:8000`. Backend wymaga ustawienia `CORS_ALLOWED_ORIGINS`
na adres frontendu, np. `["http://localhost:3000"]`.
Konfiguracja `/config` udostępnia przeglądarce wyłącznie publiczny adres API.
Frontend nie potrzebuje sekretu JWT ani danych dostępowych do PostgreSQL.
Repozytoria mogą znajdować się na różnych serwerach lub w dowolnych katalogach.

## Zachowanie

- Pusta baza: rejestracja pierwszego administratora.
- Istniejące konto: logowanie, z możliwością rejestracji kolejnego użytkownika.
- Po rejestracji przejście do logowania; po logowaniu e-mail, rola i wylogowanie.
- Ważny JWT w `sessionStorage` karty przywraca sesję po odświeżeniu.
- Niedostępność API pokazuje błąd i przycisk ponowienia.

Wylogowanie usuwa token z przeglądarki; backend nie unieważnia jeszcze JWT.

## Testy

```sh
uv run pytest
uv run ruff check .
```

Testy frontendu nie wymagają backendu ani bazy. Opcjonalny test obu aplikacji
w Chromium znajduje się w backendzie: `tests/browser_smoke.py`.


### Uruchamianie bez skryptu

Z katalogu `AI-Slop_frontend`:

```sh
uv run --no-active uvicorn main:app --reload --port 3000
```

`--no-active` jawnie wybiera środowisko projektu i usuwa ostrzeżenie o aktywnym
środowisku innego projektu. Sprawdzisz użyty interpreter poleceniem:

```sh
uv run --no-active python -c "import sys; print(sys.executable)"
```

Ścieżka powinna wskazywać `AI-Slop_frontend/.venv/bin/python`.
Przy otwarciu folderu `AI-Slop_frontend` w VS Code można użyć zadania
**Terminal → Run Task → Frontend: start**. Zadanie jawnie wybiera środowisko frontendu.
Ustawienie domyślnego interpretera dotyczy nowych wyborów w edytorze;
nie zmienia środowiska już otwartego terminala.
