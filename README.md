# FinanzManager

Ein lokaler, persönlicher Finanzmanager für eine Person. Er beantwortet eine Frage: **Wie viel Geld darf ich gerade noch ausgeben, ohne meine Ziele zu gefährden?**

Jeder Gehaltseingang startet einen neuen Budgetzeitraum und wird automatisch aufgeteilt: 20 % Sparen, 50 % Fixkosten, 30 % Freizeit. Was am Ende eines Zeitraums von Fixkosten und Freizeit übrig bleibt, wandert automatisch in die Reserve. Alles läuft auf deinem Rechner, ohne Cloud-Dienste.

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite
- Frontend: React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, React Router
- Betrieb: ein Prozess liefert API und App aus (gleiche Origin), als PWA auf dem iPhone installierbar

Die Architektur und die wichtigsten Entscheidungen beschreibt [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Voraussetzungen

- Python 3.12 oder neuer
- Node.js 22 oder neuer (nur zum Bauen der Oberfläche)
- Optional: Docker mit Docker Compose

## Schnellstart mit Docker Compose

1. Lege die Konfiguration an:

   ```bash
   cp .env.example .env
   ```

2. Baue und starte den Container:

   ```bash
   docker compose up -d --build
   ```

3. Öffne <http://localhost:8000> und lege dein Konto an.

Die Datenbank liegt in `./data/finanzmanager.db`. Standardmäßig ist die App nur auf diesem Rechner erreichbar (`FM_BIND=127.0.0.1`).

Unter Linux läuft der Container als Benutzer mit der UID 10001. Gib ihm einmalig Schreibrechte auf den Datenordner: `mkdir -p data && sudo chown 10001 data`.

## Start ohne Docker

Die folgenden Befehle zeigen PowerShell (Windows). Unter macOS oder Linux heißt der Python-Pfad `.venv/bin/python` statt `.venv\Scripts\python`.

1. Richte das Backend ein:

   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\python -m pip install -e ".[dev]"
   ```

2. Baue die Oberfläche:

   ```powershell
   cd ..\frontend
   npm ci
   npm run build
   ```

3. Starte den Server:

   ```powershell
   cd ..\backend
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

4. Öffne <http://localhost:8000>.

Beim Start legt der Server die Datenbank an und spielt alle Migrationen ein. Der Datenordner ist `backend/data/`, änderbar über `FM_DATA_DIR`.

### Entwicklungsmodus

Für Arbeit am Code laufen Backend und Vite getrennt. Vite leitet `/api` an das Backend weiter, die App nutzt also weiterhin eine Origin.

```powershell
# Terminal 1
cd backend
$env:FM_ENV = "development"; .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Die App läuft dann unter <http://localhost:5173>. Im Entwicklungsmodus gibt es die API-Dokumentation unter <http://localhost:8000/api/docs>. In Produktion ist sie abgeschaltet.

### Demo-Daten

Zum Ausprobieren füllst du eine **leere** Datenbank mit Beispieldaten. Alle Einträge tragen den Zusatz „(Demo)“.

```powershell
cd backend
$env:FM_DATA_DIR = ".\demo-data"; .venv\Scripts\python -m app.cli seed-demo
```

## Datenbank

- SQLite-Datei: `<FM_DATA_DIR>/finanzmanager.db`
- Migrationen: Alembic unter `backend/alembic/`. Der Server spielt sie beim Start automatisch ein.
- Manuell migrieren: `.venv\Scripts\python -m app.cli migrate`
- Neue Migration nach einer Modelländerung: `.venv\Scripts\alembic revision --autogenerate -m "beschreibung"`

## Zugriff vom iPhone im selben Netzwerk

1. Gib den Server im Heimnetz frei.
   - Mit Docker: setze `FM_BIND=0.0.0.0` in `.env` und starte neu mit `docker compose up -d`.
   - Ohne Docker: starte uvicorn mit `--host 0.0.0.0`.
2. Ermittle die IP-Adresse des Rechners, zum Beispiel mit `ipconfig` (Windows) oder `ip addr` (Linux).
3. Öffne auf dem iPhone in Safari `http://<IP-Adresse>:8000` und melde dich an.
4. Tippe auf **Teilen** und dann auf **Zum Home-Bildschirm**.

Über reines HTTP im Heimnetz funktioniert die App vollständig. Safari registriert dort aber keinen Service Worker, weil das eine sichere Verbindung voraussetzt. Die App-Oberfläche wird dann nicht offline zwischengespeichert. Mit HTTPS über Tailscale (nächster Abschnitt) bekommst du beides.

Wenn das iPhone die Seite nicht erreicht, blockiert meist die Firewall des Rechners den Port 8000.

## Zugriff über Tailscale (HTTPS)

Mit [Tailscale](https://tailscale.com) erreichst du die App von unterwegs, ohne sie ins Internet zu stellen. `tailscale serve` stellt ein gültiges HTTPS-Zertifikat für deinen Rechner aus.

1. Installiere Tailscale auf dem Rechner und dem iPhone und melde beide im selben Tailnet an.
2. Aktiviere in der Tailscale-Verwaltung **MagicDNS** und **HTTPS Certificates**.
3. Lass den Server auf `127.0.0.1:8000` laufen (Standard) und gib ihn über Tailscale frei:

   ```bash
   tailscale serve --bg 8000
   ```

4. Öffne auf dem iPhone `https://<rechnername>.<tailnet>.ts.net` und füge die Seite zum Home-Bildschirm hinzu.

Hinweise zu Cookies:

- `FM_COOKIE_SECURE=auto` (Standard) setzt das `Secure`-Flag, sobald eine Anfrage per HTTPS ankommt. Hinter `tailscale serve` erkennt der Server das über den Header `X-Forwarded-Proto`. Dafür startet der Docker-Container uvicorn mit `--proxy-headers`. Ohne Docker ergänzt du `--proxy-headers` selbst.
- Nutzt du die App ausschließlich über Tailscale, setze `FM_COOKIE_SECURE=true`. Dann verlassen die Sitzungs-Cookies den Rechner nie unverschlüsselt.
- Läuft der Server in Docker und Tailscale auf dem Host, kommen die Anfragen von der Docker-Bridge. Erlaube diese Adresse in `FM_FORWARDED_ALLOW_IPS`, zum Beispiel `FM_FORWARDED_ALLOW_IPS=172.16.0.0/12`, sonst ignoriert uvicorn den Header.

## Backup und Wiederherstellung

Ein Backup ist eine vollständige Kopie der SQLite-Datenbank. Es entsteht mit der SQLite-Backup-Funktion und ist auch bei laufendem Server konsistent.

- In der App: **Einstellungen → Daten und Backup → Datenbank-Backup**. Die Datei wird heruntergeladen und zusätzlich unter `<FM_DATA_DIR>/backups/` abgelegt.
- Per Kommandozeile: `.venv\Scripts\python -m app.cli backup`
- Mit Docker: `docker compose exec finanzmanager python -m app.cli backup`

So stellst du ein Backup wieder her:

1. Stoppe den Server (`docker compose stop` oder uvicorn beenden).
2. Spiele das Backup ein:

   ```powershell
   cd backend
   .venv\Scripts\python -m app.cli restore C:\pfad\zu\finanzmanager-20261013-020000.db
   ```

   Der Befehl prüft die Datei, sichert die bisherige Datenbank als `finanzmanager.vor-restore-<zeit>.db` und spielt danach fehlende Migrationen ein.
3. Starte den Server wieder.

Mit Docker kopierst du die Backup-Datei als `data/finanzmanager.db` in den Datenordner, während der Container gestoppt ist. Lösche vorher eventuell vorhandene Dateien `finanzmanager.db-wal` und `finanzmanager.db-shm`.

Zusätzlich gibt es zwei Exporte zum Lesen oder Weiterverarbeiten: alle Daten als JSON und alle Buchungen als CSV (Semikolon, für Excel).

## Passwort vergessen

Setze das Passwort direkt auf dem Rechner zurück. Alle Sitzungen werden dabei beendet.

```powershell
cd backend
.venv\Scripts\python -m app.cli reset-password <benutzername>
```

## Tests und Prüfungen

| Prüfung | Befehl | Ordner |
|---|---|---|
| Backend-Tests (pytest, inklusive des Pflicht-Szenarios 1.300 € → 1.500 €) | `.venv\Scripts\python -m pytest` | `backend` |
| Lint und Format | `.venv\Scripts\ruff check app tests` | `backend` |
| Typprüfung | `.venv\Scripts\mypy app` | `backend` |
| Frontend-Unit-Tests | `npm test` | `frontend` |
| TypeScript | `npm run typecheck` | `frontend` |
| Lint | `npm run lint` | `frontend` |
| Produktionsbuild | `npm run build` | `frontend` |
| End-to-End im Browser (iPhone-Ansicht) | `npm ci`, `npx playwright install chromium`, `npm test` | `e2e` |
| Daten überstehen einen Neustart | `backend\.venv\Scripts\python scripts\verify_restart.py` | Projektwurzel |

Der End-to-End-Test braucht eine gebaute Oberfläche (`frontend/dist`). Er startet den echten Server mit leerer Datenbank und spielt die Akzeptanzkriterien 1 bis 15 durch. Screenshots landen in `e2e/artifacts/shots/`.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen mit dem Präfix `FM_` oder aus einer `.env`-Datei. Die vollständige Liste mit Erklärungen steht in [.env.example](.env.example). Es gibt keine Passwörter oder Schlüssel im Code. Das Konto legst du beim ersten Start in der App an.

## Projektstruktur

```text
FinanzManager/
├── backend/
│   ├── app/
│   │   ├── domain/        Reine Geschäftslogik ohne Datenbank: Aufteilung, Abschluss, Warnungen, Tagesbudget
│   │   ├── models/        SQLAlchemy-Modelle und Constraints
│   │   ├── schemas/       Pydantic-Schemas der API
│   │   ├── services/      Anwendungslogik: Perioden, Buchungen, Reserve, Sparen, Statistik, Auth
│   │   ├── api/           FastAPI-Router, Authentifizierung, CSRF
│   │   ├── integrations/  Schnittstellen für Phase 2 und 3 (Gehaltsabrechnung, Bankimport, KI)
│   │   ├── db/            Engine, Basistypen, Migrationsaufruf
│   │   └── cli.py         Backup, Restore, Passwort, Demo-Daten
│   ├── alembic/           Migrationen
│   └── tests/             pytest
├── frontend/
│   ├── src/pages/         Die acht Bereiche der App
│   ├── src/components/    Dialoge, Diagramme, Layout, shadcn/ui
│   └── src/lib/           API-Client, Typen, Formatierung, Queries
├── e2e/                   Playwright-Tests gegen den echten Server
├── scripts/               Prüfskripte
├── docs/ARCHITECTURE.md
├── decisions.tsv          Entscheidungsprotokoll der Entwicklung
├── Dockerfile
└── docker-compose.yml
```

## Bekannte Einschränkungen

- **Keine Offline-Datenhaltung.** Der Service Worker speichert nur die App-Oberfläche. Finanzdaten kommen immer live vom Server und werden nie im Browser-Cache abgelegt. Ohne Verbindung zum Server zeigt die App einen Fehler statt veralteter Zahlen. Eine Offline-Synchronisation gibt es nicht.
- **Ein Benutzer.** Die App ist für genau ein Konto gebaut.
- **Ein Budgetmodell.** Nur 20/50/30 ist hinterlegt. Weitere Modelle lassen sich im Code ergänzen (`backend/app/domain/budget_models.py`), eine Auswahl in der Oberfläche fehlt noch.
- **Sparziele und Stornos.** Wird eine Umbuchung aus dem Sparen storniert, kommt das Geld als freies Erspartes zurück, nicht automatisch ins ursprüngliche Sparziel. Wer ein Sparziel löscht, gibt dessen Zuweisungen frei.
- **Gehälter sind nicht stornierbar.** Ein Tippfehler im aktuellen Gehalt lässt sich über **Budget → Gehalt korrigieren** beheben. Einen Periodenwechsel rückgängig zu machen ist nicht vorgesehen. Dafür ist das Backup da.
- **Keine Push-Benachrichtigungen.** Warnungen erscheinen in der App.
- **Phase 2 und 3 sind vorbereitet, nicht gebaut.** PDF-Gehaltsabrechnung, Bankimport und KI-Assistent existieren nur als Schnittstellen in `backend/app/integrations/`. Es werden keine Bankzugangsdaten abgefragt oder gespeichert.
- **Kein HTTPS im Server selbst.** Für verschlüsselten Zugriff von anderen Geräten nutze Tailscale oder einen anderen Reverse Proxy.
