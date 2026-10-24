# Plan: polytess Mobile — das Board auf dem Handy mitverfolgen

Stand: 2026-10-24 · Basis: polytess Viewer v1.18 (Board-Kern
`graph/board.py` mit `BoardRunner`-Events, Lauf-Zustand `<flow>.board.json`,
Dashboard-Statistik `BoardState.summary`)

> **Status: Phasen 1–3 UMGESETZT** (2026-10-24, v1.19.0):
> `polytess/viewer/mobile_server.py` (aiohttp, Token, WebSocket-Deltas,
> Log-Puffer, Steuer-Endpunkte), `share_dialog.py` (QR per QPainter,
> Adresswahl, Freigabe-Schalter, neuer Code), `assets/mobile/`
> (Board, Dashboard, Kartendetail mit Log, Reconnect, Banner/Vibration,
> Vorgänger-Auswahl). Offen: Phase 4 (HTTPS, PWA-Installation, Web-Push,
> Relay), E-Mail-Hinweis bei Fertig.

---

## 1. Zielbild

Im Viewer läuft ein Hauptprozess. Der Anwender tippt auf **"Auf dem Handy
verfolgen"**, der Viewer zeigt einen **QR-Code**. Das Handy fotografiert
ihn mit der Kamera-App, öffnet die Seite und zeigt dasselbe Board —
live: Karten wandern von Backlog nach In Progress nach Done, Fortschritt
und Log-Ende laufen mit, das Dashboard zeigt Restzeit und Fehler. Wenn
der Prozess fertig ist oder eine Karte scheitert, meldet sich das Handy.
Optional (abschaltbar, Standard aus) kann vom Handy aus gestartet und
gestoppt werden.

## 2. Was man dafür braucht — die Entscheidung

Drei Dinge entscheiden alles: **wo die Daten liegen**, **wie das Handy
sie erreicht** und **womit die Handy-Seite gebaut wird**.

### 2.1 Daten: der Viewer ist die Quelle
Der Viewer hat bereits alles, was das Handy zeigen soll:
`board_spec` (Karten, Abhängigkeiten), `BoardState` (Status, Dauer,
Historie), `summary()` (Dashboard-Zahlen) und die `on_change` /
`on_progress`-Events des `BoardRunner`. Es muss nichts neu berechnet
werden, nur **nach außen gereicht**.

### 2.2 Erreichbarkeit: lokaler Server im Viewer, Handy im selben Netz
| Variante | Wie | Bewertung |
|---|---|---|
| **A · Lokaler Server im Viewer** | Der Viewer startet einen kleinen HTTP+WebSocket-Server (`aiohttp`, läuft im vorhandenen asyncio/qasync-Loop). QR = `http://<IP>:<Port>/m/<Token>`. Handy im selben WLAN/VPN. | **Empfohlen.** Keine Infrastruktur, keine Daten verlassen das Firmennetz, 1–2 Sessions Aufwand. Grenze: Handy muss den Rechner erreichen (Firmen-WLAN/VPN, Firewall-Freigabe des Ports). |
| B · Relay-Dienst | Viewer schiebt Zustand zu einem Cloud/Intranet-Relay, Handy liest dort. | Funktioniert auch unterwegs ohne VPN. Braucht Betrieb eines Dienstes, Datenschutz-/Security-Freigabe, Auth. Später als Option, wenn A im Alltag an der Netzgrenze scheitert. |
| C · Datei-Share | `board.json` auf ein Netzlaufwerk, Handy-App pollt. | Keine Live-Events, Dateizugriff vom Handy ist in Firmen meist nicht möglich. Nein. |

### 2.3 Handy-Seite: Web-App statt Store-App
| Variante | Bewertung |
|---|---|
| **Web-App (PWA-fähig), vom Viewer selbst ausgeliefert** | **Empfohlen.** QR → Browser → fertig. Kein App-Store, keine Signierung, keine Geräteverwaltung. Dunkles Design wie der Viewer, ein HTML+JS-Bundle ohne Build-Schritt unter `polytess/assets/mobile/`. "Zum Home-Bildschirm" möglich. |
| Native App (Flutter / React Native / Swift+Kotlin) | Nötig nur für zuverlässige Push-Benachrichtigungen bei geschlossener App und Hintergrund-Sync. Store-Prozess, Signierung, zwei Plattformen, Firmen-MDM. Phase 4, falls die Web-App nicht reicht. |

Konsequenz: **A + Web-App.** Die native App bleibt Option.

## 3. Architektur

```
Viewer (Desktop)                              Handy
┌──────────────────────────────┐              ┌──────────────────────┐
│ BoardPage ── BoardRunner     │   WLAN/VPN   │ Browser / PWA        │
│      │ on_change/on_progress │◄────────────►│  /m/<token>          │
│ MobileServer (aiohttp)       │  HTTP + WS   │  Board, Dashboard,   │
│  GET  /api/board             │              │  Log-Ende, Toasts    │
│  WS   /api/events            │              │  (optional: Start/   │
│  GET  /api/log/<card>        │              │   Stop-Buttons)      │
│  POST /api/cards/<id>/start  │  (optional)  │                      │
│  QR-Dialog (URL + Token)     │              │                      │
└──────────────────────────────┘              └──────────────────────┘
```

- **MobileServer** (`polytess/viewer/mobile_server.py`): startet auf
  0.0.0.0 und einem freien Port (Standard 8765, einstellbar), erzeugt
  pro Viewer-Sitzung ein zufälliges Token. Jede Anfrage ohne gültiges
  Token → 404. Hält die Liste verbundener Handys (für die Anzeige
  "1 Gerät verbunden" im Viewer).
- **Events**: Der Server hängt sich an `BoardRunner.on_change` /
  `on_progress` und an das Log des laufenden Karten-Runs; jede Änderung
  wird als JSON über den WebSocket gesendet (`{"type":"card",
  "guid":…, "status":…}`, `{"type":"progress", …}`, `{"type":"log",
  "card":…, "line":…}`, `{"type":"summary", …}`). Beim Verbinden
  bekommt das Handy den Vollzustand (`/api/board` = spec + state +
  summary), danach nur Deltas; bei Verbindungsabbruch reconnect mit
  Vollzustand.
- **Flow-Wechsel im Viewer**: Server bleibt, sendet
  `{"type":"flow", …}`; das Handy folgt dem gerade offenen Board. Ohne
  offenes Board zeigt das Handy "Warten auf den Viewer".
- **Steuerung** (Phase 3): `POST /api/cards/<guid>/start|stop`,
  `/api/run-all`. Nur aktiv, wenn im Viewer "Steuerung vom Handy
  erlauben" eingeschaltet ist; Vorgänger-Dialog wird auf dem Handy als
  Auswahl gestellt (in order / only this / cancel).
- **QR-Code**: Paket `qrcode` (reines Python, SVG-Ausgabe ohne Pillow)
  → im Viewer als Dialog "Auf dem Handy verfolgen" mit QR, Klartext-URL,
  Gerätezähler und Schalter für die Steuerung. Die IP wird aus den
  aktiven Netzschnittstellen ermittelt (bei mehreren: Auswahl im
  Dialog, z.B. WLAN vs. VPN-Adapter).
- **Handy-Seite** (`polytess/assets/mobile/index.html` + `app.js` +
  `style.css`): eine Seite, vertikal — oben Fortschrittsring und
  Zähler, dann die drei Spalten als untereinander liegende Abschnitte
  (Handy ist hochkant), Karte antippen → Detail mit Beschreibung,
  Dauer, letzten 50 Log-Zeilen. Dunkles Theme mit den Viewer-Farben,
  dieselben Status-Farben. Bei Done/Failed: Vibration (`navigator.
  vibrate`, Android), kurzer Ton, Banner oben. Kein Framework, kein
  Build.
- **Abhängigkeiten**: `pip install polytess[mobile]` →
  `aiohttp`, `qrcode`. Ohne die Pakete bleibt der Button im Viewer
  ausgegraut mit Hinweis. Exe-Bundle nimmt beide mit.

## 4. Sicherheit und Netz

- **Token im QR** ist das Geheimnis: 128 Bit zufällig, pro Viewer-Start
  neu; ohne Token keine Antwort, auch keine Fehlermeldung, die das
  Vorhandensein verrät. "Neuen QR erzeugen" macht alte Links ungültig.
- **Nur lesen** ist Standard. Steuerung ist ein bewusster Schalter im
  Dialog und wird im Viewer-Log protokolliert ("Start Mesh vom Handy").
- **Transport**: Phase 1–3 laufen über HTTP im Firmennetz. Das reicht
  für das Mitverfolgen; Engineering-Zahlen sind in Log-Zeilen sichtbar,
  deshalb kein Betrieb über ungesicherte Gäste-WLANs — steht im
  Handbuch. HTTPS mit firmeneigenem Zertifikat (oder `mkcert` für den
  Einzelplatz) ist in Phase 4 vorgesehen; es ist Voraussetzung für
  "Zum Home-Bildschirm" mit Service-Worker und für Web-Push.
- **Firewall**: Beim ersten Start fragt Windows nach der Freigabe; das
  Handbuch erklärt es. Port einstellbar, falls IT eine Vorgabe macht.
- **Datensparsamkeit**: Das Handy bekommt Kartennamen, Status, Dauern,
  Zusammenfassung und Log-Zeilen des gewählten Laufs — keine
  Variablenwerte außer denen, die in Log-Zeilen stehen, keine
  Dateiinhalte.

## 5. Benachrichtigungen — ehrlich eingeordnet

- **Seite offen** (Handy entsperrt, Browser vorne): Banner, Vibration,
  Ton — sofort machbar, Phase 2.
- **Seite im Hintergrund / Handy gesperrt**: Browser schlafen ein. Web-
  Push braucht HTTPS, einen Service-Worker und einen Push-Dienst
  (Apple/Google); auf iOS nur für installierte PWAs ab 16.4. Das ist
  Phase 4 und lohnt nur, wenn A im Alltag läuft.
- **Pragmatische Brücke ab Phase 2**: die bestehende E-Mail-Funktion
  (`report_email`, Send Email) und optional ein "Fertig-Hinweis per
  Mail" im Viewer — das Handy bekommt die Mail auch gesperrt.

## 6. Änderungen im Repo (Übersicht)

| Bereich | Neu / geändert |
|---|---|
| `polytess/viewer/mobile_server.py` | aiohttp-Server, Token, WS-Broadcast, Log-Puffer je Karte, Steuer-Endpunkte |
| `polytess/viewer/board_page.py` | hängt den Server an Runner-Events; Button "Auf dem Handy verfolgen"; Statuszeile "n Geräte" |
| `polytess/viewer/share_dialog.py` | QR (SVG), URL, Netzschnittstellen-Auswahl, Schalter Steuerung, "Neuen QR" |
| `polytess/assets/mobile/` | index.html, app.js, style.css (Board, Dashboard, Detail, Reconnect) |
| `polytess/core/app_settings.py` | `mobile_port`, `mobile_allow_control`, `mobile_interface` |
| `pyproject.toml` / `build_exe.py` | Extra `mobile = ["aiohttp", "qrcode"]`, Assets ins Bundle |
| Tests | Server mit `aiohttp` Test-Client: Vollzustand, Delta nach `on_change`, Token-Schutz, Steuerung nur bei Freigabe; Smoke-Test des Dialogs offscreen |
| Handbuch | Kapitel 10 bekommt Abschnitt "Auf dem Handy verfolgen" inkl. Firewall/Netz-Hinweise |

## 7. Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **1 · Server + QR** | `mobile_server.py` mit `/api/board`, `/api/events`, Token; Share-Dialog mit QR; Settings; Tests | Handy kann JSON-Zustand live sehen (noch ohne schöne Seite) |
| **2 · Handy-Seite** | `assets/mobile/`: Board, Dashboard, Kartendetail mit Log-Ende, Reconnect, Vibration/Ton/Banner bei Done/Failed, Flow-Wechsel folgt | **Ziel des Users erreicht: QR fotografieren, Board live verfolgen** |
| **3 · Steuerung** | Start/Stop/Run all vom Handy mit Freigabe-Schalter, Vorgänger-Dialog auf dem Handy, Protokollierung im Viewer | Handy als Fernbedienung |
| **4 · Außerhalb des Netzes** | HTTPS (Firmen-Zertifikat/mkcert), PWA-Installation, Web-Push; alternativ Relay-Dienst; evtl. native Hülle | Benachrichtigungen bei gesperrtem Handy, Nutzung ohne VPN |

Aufwand: Phase 1 ≈ 1–2 Sessions, Phase 2 ≈ 2, Phase 3 ≈ 1, Phase 4
≈ 3+ und abhängig von IT-Entscheidungen (Zertifikat, Relay-Betrieb).

## 8. Offene Fragen an den User / die IT

- Sind Rechner und Handy im selben Netz (Firmen-WLAN oder VPN auf dem
  Handy)? Sonst ist Variante B (Relay) nötig.
- Darf der Viewer-Rechner einen Port öffnen (Firewall-Regel)?
- Reicht "mitverfolgen" (Lesen), oder soll das Handy von Anfang an
  steuern dürfen?
- Gibt es ein Firmen-Zertifikat für interne HTTPS-Dienste (Phase 4)?
