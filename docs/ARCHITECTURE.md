# Architektur und Entscheidungen

Dieses Dokument erklärt, wie der FinanzManager rechnet und warum er so gebaut ist. Wie du ihn installierst und betreibst, steht im [README](../README.md). Das chronologische Protokoll aller Entscheidungen während der Entwicklung liegt in [decisions.tsv](../decisions.tsv).

## Das Backend rechnet, die Oberfläche zeigt an

Jede Zahl, die die App anzeigt, berechnet das Backend: Budgets, Verbrauch, Reserve, Sparquote, Tagesbudget und Warnungen. Die Oberfläche formatiert nur. Dadurch gibt es genau eine Stelle, an der eine Rechenregel stimmen muss, und die automatisierten Tests prüfen genau diese Stelle über die HTTP-API.

Das Backend hat drei Schichten:

- `app/domain/` enthält reine Funktionen ohne Datenbank: die Aufteilung nach Budgetmodell, den Periodenabschluss, das Tagesbudget, Fälligkeiten von Fixkosten und die Warnregeln. Diese Funktionen sind ohne Server testbar.
- `app/services/` setzt die Regeln mit der Datenbank um. Hier liegen der Periodenwechsel, Buchungen, Korrekturen, Reserve und Sparen.
- `app/api/` ist eine dünne HTTP-Schicht. Sie prüft Anmeldung und CSRF, ruft einen Service auf und schreibt die Transaktion fest.

## Geld ist eine ganze Zahl in Cent

Beträge sind überall `int` in Cent: in der Datenbank, in der API und im Frontend-State. Erst die Anzeige macht daraus „1.300,00 €“. Prozentwerte überträgt die API als Basispunkte, also 4523 für 45,23 %. So entsteht nirgends ein Rundungsfehler durch Gleitkommazahlen, und ein JSON-Wert kann nicht als String oder Zahl unterschiedlich gelesen werden.

Die Aufteilung nach 20/50/30 nutzt das Verfahren des größten Rests. Jeder Topf bekommt zuerst den abgerundeten Anteil. Die übrigen Cent gehen an die Töpfe mit dem größten Nachkommarest. Die drei Töpfe ergeben damit immer exakt das Nettogehalt. Ein Test prüft das für viele Beträge.

Budgetmodelle stehen in einer Tabelle (`BUDGET_MODELS` in `app/domain/budget_models.py`). Ein neues Modell ist ein neuer Eintrag. Jede Periode speichert, mit welchem Modell sie aufgeteilt wurde.

## Eine Budgetperiode beginnt mit dem Gehalt

Eine Periode läuft vom Zeitpunkt eines Gehaltseingangs bis unmittelbar vor dem nächsten, nicht von Monatsanfang bis Monatsende. Eine Buchung gehört zu der Periode, in deren Zeitraum ihr Datum fällt.

Höchstens eine Periode ist aktiv. Das sichert nicht nur der Code, sondern die Datenbank selbst über einen partiellen eindeutigen Index (`uq_budget_periods_single_active`). Ein CHECK-Constraint sorgt dafür, dass eine abgeschlossene Periode immer ein Ende und ein festgeschriebenes Ergebnis hat.

### Der Periodenwechsel ist eine einzige Transaktion

`_close_and_open` in `app/services/periods.py` erledigt den Wechsel in einer Datenbanktransaktion:

1. Die aktive Periode wird geschlossen.
2. Buchungen, die zeitlich nach dem neuen Gehalt liegen, wandern in die neue Periode.
3. Wenn gewünscht, deckt die Reserve ein Defizit, sichtbar als eigene Umbuchung.
4. Das Ergebnis wird berechnet und festgeschrieben, und die Reserve erhält ihre Gutschrift.
5. Die neue Periode wird angelegt und das Gehalt nach Modell aufgeteilt.
6. Der Sparanteil wird ins Sparbuch gebucht.

Schlägt ein Schritt fehl, wird alles zurückgerollt. SQLite-Transaktionen starten mit `BEGIN IMMEDIATE`. Zwei gleichzeitige Gehaltsbuchungen warten deshalb aufeinander, statt beide „keine Gutschrift bisher“ zu lesen.

Die Vorschau im Gehaltsdialog führt exakt diesen Wechsel in einem SAVEPOINT aus und rollt ihn danach zurück. Vorschau und tatsächliche Buchung können dadurch nicht voneinander abweichen.

### So entsteht die Reserve-Gutschrift

Beim Abschluss werden die Reste von Fixkosten und Freizeit verrechnet. Ein überzogener Topf mindert den Rest des anderen. Ist die Summe positiv, geht sie in die Reserve. Ist sie negativ, entsteht ein Defizit ohne jede Gutschrift. Der Sparanteil gehört nicht zu dieser Rechnung, er liegt bereits im Sparbuch.

Ein Beispiel mit 1.300 € Gehalt: Fixkosten 650 € geplant, 600 € ausgegeben. Freizeit 390 € geplant, 300 € ausgegeben. Die Reserve erhält 50 € + 90 € = 140 €. Die 260 € Sparanteil bleiben davon getrennt.

Ein Defizit deckt die Reserve nur, wenn du das ausdrücklich wählst. Die Deckung ist eine normale Umbuchung von der Reserve ins Budget der Periode. Dadurch bleibt sie im Protokoll sichtbar.

## Reserve und Sparen sind Kontobücher

Reserve und Sparen speichern keinen Kontostand. Jede Bewegung ist eine Zeile in `reserve_entries` oder `savings_entries`, und der Stand ist die Summe aller Zeilen. Zeilen werden nie geändert. Ein Fehler wird mit einer neuen Gegenbuchung korrigiert. So lässt sich jeder Euro bis zu seiner Ursache zurückverfolgen.

Doppelte Gutschriften verhindert die Datenbank: Pro Periode gibt es höchstens eine Abschlussgutschrift (`uq_reserve_entries_period_close`) und höchstens eine Sparanteil-Buchung (`uq_savings_entries_period_savings`).

Das Budget einer Periode ist ebenfalls eine Summe: die Zeilen in `budget_allocations`. Gehaltsaufteilung, weitere Einnahmen, Umbuchungen aus der Reserve und Stornos sind jeweils eigene Zeilen. Der Abschluss braucht dadurch nur eine Formel, egal woher das Geld kam.

Sparziele erzeugen kein Geld. Eine Zuweisung an ein Sparziel markiert einen Teil des vorhandenen Ersparten. Die Summe aller Zuweisungen darf das Ersparte nie übersteigen. Das Vermögen erscheint deshalb nie doppelt.

## Umbuchungen schaffen kein Geld

Eine Umbuchung, etwa von der Reserve ins Sparen, ist weder Einnahme noch Ausgabe. Sie besteht aus zwei gleich großen Zeilen mit entgegengesetztem Vorzeichen in zwei Töpfen. Die Summe über alle Töpfe bleibt gleich. Ein Test prüft genau das. Eine Umbuchung aus einem Topf ist nur bis zu dessen verfügbarem Stand erlaubt.

## Abgeschlossene Perioden ändern sich nie still

Trägst du nachträglich eine Ausgabe in eine abgeschlossene Periode ein, änderst oder löschst du eine, ändert sich deren Ergebnis. Damit ändert sich auch, was die Reserve hätte bekommen müssen.

`settle_closed_periods` behandelt das in drei Schritten:

1. Vor der Änderung hält das Backend den Stand jedes Topfs der betroffenen abgeschlossenen Perioden fest (`snapshot_closed`). Dann führt es die Änderung aus und vergleicht. Jede Abweichung zählt, auch eine, die nur Geld zwischen Fixkosten und Freizeit verschiebt und das Ergebnis gleich lässt.
2. Ohne Bestätigung antwortet es mit HTTP 409 (`closed_period_correction_required`) und schickt die Auswirkung mit: Ergebnis vorher, Ergebnis nachher, Änderung der Reserve. Die Transaktion wird verworfen.
3. Die Oberfläche zeigt diese Zahlen. Bestätigst du, wiederholt sie die Anfrage mit `confirm_correction`. Das Backend bucht dann die Differenz als Korrekturzeile in der Reserve, schreibt einen Prüfeintrag in `period_corrections` und aktualisiert das festgeschriebene Ergebnis.

Eine bestätigte Korrektur darf die Reserve ins Minus bringen, denn das Geld ist bereits ausgegeben. Der Dialog zeigt den Reservestand danach, und das Dashboard warnt, solange die Reserve negativ ist.

Die Reserve-Differenz folgt der Abschlussregel. Wird aus 140 € Rest durch eine Nachbuchung ein Defizit von 10 €, verliert die Reserve 140 €, nicht 150 €.

Einnahmen und Umbuchungen werden nicht gelöscht, sondern storniert. Das Storno erzeugt gespiegelte Zeilen in allen betroffenen Büchern. Ausgaben dürfen bearbeitet und gelöscht werden, in abgeschlossenen Perioden nur über die Korrekturbestätigung.

## Doppeltes Absenden ist harmlos

Jeder Dialog, der Geld bewegt, erzeugt beim Öffnen einen zufälligen `Idempotency-Key` und schickt ihn mit. Das Backend speichert die Antwort zu diesem Schlüssel in derselben Transaktion wie die Buchung (`idempotency_keys`). Ein zweiter Klick, ein Retry nach Netzwerkfehler oder zwei parallele Anfragen bekommen dieselbe Antwort, und es entsteht nichts doppelt. Kommt derselbe Schlüssel mit anderem Inhalt, lehnt das Backend mit 409 ab.

Zusätzlich lehnt das Backend ein Gehalt ab, das nicht nach dem Beginn der aktiven Periode liegt. Ein versehentlich zweimal erfasstes Gehalt mit gleichem Zeitpunkt scheitert so auch ohne Schlüssel.

## Geplante Fixkosten sind keine Ausgaben

Ein Eintrag unter Fixkosten ist ein Plan. Er zählt nie als Ausgabe. Zur Ausgabe wird er erst durch eine Buchung, die mit dem Plan verknüpft ist: per **Bezahlt buchen** oder durch Zuordnung im Ausgabe-Dialog. „Offen“ ist die Zahl der in der Periode fälligen Termine minus die Zahl der verknüpften Zahlungen. Eine Zahlung reduziert also den offenen Betrag und erhöht die tatsächlichen Fixkosten, aber nie beides doppelt.

Ohne erwarteten Zahltag nimmt die Fixkostenübersicht einen Monat ab Periodenbeginn als Zeitraum an und sagt das ausdrücklich. Das Tagesbudget für Freizeit zeigt die App ohne Zahltag dagegen gar nicht, weil es sonst eine erfundene Prognose wäre.

## Sicherheit

- **Anmeldung.** Ein Konto, Passwort mit Argon2id gehasht. Nach fünf Fehlversuchen sperrt die Anmeldung für fünf Minuten.
- **Sitzungen.** Ein zufälliges Token im Cookie `fm_session` mit `HttpOnly` und `SameSite=Strict`. Die Datenbank speichert nur den SHA-256-Hash. Ein Datenbankleck verrät damit keine gültige Sitzung. Eine Passwortänderung beendet alle anderen Sitzungen.
- **CSRF.** Double-Submit: Das Cookie `fm_csrf` ist für die App lesbar. Jede schreibende Anfrage muss den Wert im Header `X-CSRF-Token` mitschicken, und das Backend vergleicht ihn mit dem Wert der Sitzung.
- **Secure-Cookies.** `FM_COOKIE_SECURE=auto` setzt das Flag, sobald die Anfrage per HTTPS ankommt.
- **Caching.** Alle API-Antworten tragen `Cache-Control: no-store`. Der Service Worker cacht nur statische Dateien und leitet `/api` nie aus dem Cache.
- **Header.** Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` und eine restriktive Permissions-Policy.
- **Produktion.** API-Dokumentation und OpenAPI-Schema gibt es nur mit `FM_ENV=development`.
- **CORS.** Standardmäßig aus, weil App und API dieselbe Origin haben. Bei Bedarf über `FM_CORS_ORIGINS` einschaltbar.
- **Netz.** Docker bindet standardmäßig nur an `127.0.0.1`. Der Zugriff aus dem Heimnetz muss ausdrücklich eingeschaltet werden.

## Datenmodell

| Tabelle | Zweck |
|---|---|
| `users`, `sessions` | Konto und serverseitige Sitzungen |
| `settings` | Genau eine Zeile: Budgetmodell, Reserve-Mindesthöhe, Schwelle für große Ausgaben, Verwendungszwecke der Reserve |
| `categories` | Kategorien je Art (Freizeit, Fixkosten, Einnahmen), eindeutig je Art und Name |
| `budget_periods` | Gehaltsperioden mit Status, Zeitraum und festgeschriebenem Ergebnis |
| `budget_allocations` | Zeilen, deren Summe das Budget je Topf und Periode ergibt |
| `transactions` | Ausgaben, Einnahmen (Gehalt und weitere) und Umbuchungen. CHECK-Constraints erzwingen die gültige Form je Typ. |
| `recurring_expenses` | Geplante Fixkosten mit Intervall und optionalem Fälligkeitsdatum |
| `reserve_entries` | Kontobuch der Reserve |
| `savings_entries` | Kontobuch der Ersparnisse |
| `savings_goals`, `savings_allocations` | Sparziele und die Zuweisung von Erspartem an sie |
| `period_corrections` | Prüfprotokoll jeder Korrektur einer abgeschlossenen Periode |
| `idempotency_keys` | Gespeicherte Antworten zur Abwehr doppelter Anfragen |

Die Anforderung nennt eine eigene Entität `Income`. Hier ist eine Einnahme eine `transaction` mit `type = 'income'` und `income_kind` (`salary` oder `other`). So erscheinen alle Bewegungen in einer durchsuchbaren Liste. Das Gehalt eröffnet die Periode, weitere Einnahmen landen je nach Wahl im Budget, in der Reserve oder im Sparen.

Zeitpunkte speichert die Datenbank in UTC. Kalenderlogik wie Fälligkeiten und „heute“ rechnet in Europe/Berlin. Zeitangaben ohne Zeitzone von der Oberfläche gelten als Berliner Ortszeit.

## Oberfläche

- **Routing und Daten.** React Router für die acht Bereiche. TanStack Query lädt alle Daten. Nach jeder schreibenden Aktion lädt die App alle Finanzdaten neu, weil eine Buchung mehrere Zahlen zugleich verändern kann.
- **Häufige Aufgaben.** „Ausgabe erfassen“ und „Gehalt erfassen“ sind von jeder Seite mit einem Tipp erreichbar: der Plus-Button in der mobilen Navigation und die Buttons in der Seitenleiste.
- **Dialoge.** Auf dem Desktop zentrierte Dialoge, auf dem Telefon Bottom Sheets.
- **Farben.** Sparen grün, Fixkosten blau, Freizeit orange. Die Werte wurden mit einem Farbsehschwäche-Prüfer für hell und dunkel validiert. Weil das helle Grün unter 3:1 Kontrast liegt, stehen Topf-Farben immer neben einer Textbeschriftung.
- **Geldeingabe.** Deutsche Schreibweise: „1.300,00“, „2.000“ und „12,5“ werden korrekt gelesen. „12.50“ gilt als Dezimalzahl.

## Vorbereitet für Phase 2 und 3

`app/integrations/` enthält Schnittstellen, aber keine simulierte Funktion:

- `payslip.py` definiert `PayslipParser`. Ein Parser schlägt nur einen Nettobetrag vor. Gebucht wird über den normalen Gehaltsdialog, nachdem du bestätigt hast.
- `bank_import.py` definiert `StatementSource` für CSV-Importe und später FinTS oder PSD2, dazu `dedup_key`. Der Schlüssel landet im eindeutigen Feld `transactions.external_ref`, sodass ein doppelter Import keine doppelten Buchungen erzeugt. `account_ref` unterscheidet mehrere Konten. Zugangsdaten werden nicht gespeichert.
- `assistant.py` baut mit `build_snapshot` einen schreibgeschützten Datenauszug aus den berechneten Kennzahlen. Ein späteres lokales Modell bekommt nur diesen Auszug und keine Datenbankverbindung. Es kann erklären und Vorschläge machen, aber keine Salden erfinden oder ändern.
