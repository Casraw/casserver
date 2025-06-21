# Confirmation Tracking Feature

## Überblick
Das System verfolgt jetzt in Echtzeit die Bestätigungen für sowohl Cascoin- als auch Polygon-Transaktionen und zeigt sie im Frontend mit einer Live-Fortschrittsanzeige an.

## Frontend Features

### Bestätigungsanzeige
- **Numerische Anzeige**: Zeigt "1/12", "2/12", etc. für aktuelle vs. erforderliche Bestätigungen
- **Farbkodierung**: 
  - Gelb/Orange: Noch nicht genügend Bestätigungen
  - Grün: Vollständig bestätigt
- **Fortschrittsbalken**: Visueller Balken, der den Bestätigungsfortschritt anzeigt
- **Live-Updates**: Aktualisiert sich automatisch über WebSocket-Verbindungen

### Unterstützte Transaktionstypen
1. **CAS Deposits**: Cascoin → wCAS auf Polygon
2. **Polygon Transactions**: wCAS → CAS zurück zu Cascoin
3. **Return Intentions**: wCAS Return-Absichten

## Backend Änderungen

### Datenbank-Schema
Neue Spalten in beiden Tabellen:
- `current_confirmations`: Aktuelle Anzahl der Bestätigungen
- `required_confirmations`: Erforderliche Anzahl (standardmäßig 12)
- `deposit_tx_hash`: Transaction Hash für Cascoin-Einzahlungen

### Watcher-Updates
- **Cascoin Watcher**: Verfolgt unbestätigte Transaktionen und aktualisiert Bestätigungen
- **Polygon Watcher**: Verfolgt Polygon-Transaktionen und deren Bestätigungen
- **WebSocket-Benachrichtigungen**: Sendet Live-Updates an das Frontend

### API-Endpunkte
Neue interne Endpunkte für WebSocket-Benachrichtigungen:
- `/internal/notify_deposit_update`
- `/internal/notify_polygon_transaction_update`

## Migration

### Automatische Migration (Empfohlen)
Das System führt jetzt automatisch alle notwendigen Datenbankmigrationen beim Start aus:

**Bei Docker-Start:**
```bash
docker-compose up -d  # Migrationen werden automatisch ausgeführt
```

**Bei manueller Ausführung:**
```bash
python run_migrations.py  # Führt alle Migrationen aus
```

**Bei App-Start:**
- FastAPI Anwendung führt Migrationen automatisch beim Start aus
- `backend.init_db` führt Migrationen automatisch aus

### Manuelle Migration (Falls nötig)
Falls Sie die Migration manuell ausführen möchten:

```bash
# Option 1: Eigenständiges Migrationsskript
python run_migrations.py

# Option 2: Datenbankinitialisierung (inkl. Migrationen)
python -m backend.init_db

# Option 3: Direkte SQL-Migration (nicht empfohlen)
psql -d cascoin_bridge -f database/add_confirmation_columns.sql
```

### Für neue Installationen
Die neuen Spalten werden automatisch bei der Datenbankinitialisierung erstellt.

### Migration-Sicherheit
- **Idempotent**: Migrationen können sicher mehrfach ausgeführt werden
- **Spalten-Prüfung**: System prüft, ob Spalten bereits existieren
- **Automatische Defaults**: Bestehende Datensätze erhalten automatisch Standardwerte
- **Database-Agnostic**: Funktioniert mit PostgreSQL und SQLite

## Konfiguration

### Umgebungsvariablen
- `CONFIRMATIONS_REQUIRED`: Erforderliche Bestätigungen für Cascoin (Standard: 12)
- `POLYGON_CONFIRMATIONS_REQUIRED`: Erforderliche Bestätigungen für Polygon (Standard: 12)

### Docker Compose
Die Standardwerte sind bereits in `docker-compose.prod.yml` konfiguriert.

## Verwendung

### Im Frontend
1. Öffnen Sie eine der Bridge-Seiten (cas_to_poly.html oder poly_to_cas.html)
2. Starten Sie eine Bridge-Transaktion
3. Beobachten Sie die Live-Bestätigungsanzeige im Response-Bereich

### Entwicklung
Das Feature funktioniert sowohl in der Entwicklungsumgebung als auch in der Produktion. WebSocket-Verbindungen verwenden automatisch das richtige Protokoll (ws:// für HTTP, wss:// für HTTPS).

## Fehlerbehebung

### WebSocket-Verbindungsprobleme
- Überprüfen Sie die Browser-Konsole auf WebSocket-Fehler
- Stellen Sie sicher, dass der Backend-Service läuft
- Überprüfen Sie die CORS-Konfiguration

### Bestätigungen werden nicht aktualisiert
- Überprüfen Sie die Watcher-Logs in den Docker-Containern
- Stellen Sie sicher, dass die RPC-Verbindungen zu den Blockchain-Knoten funktionieren
- Überprüfen Sie die interne API-Schlüssel-Konfiguration

## Technische Details

### WebSocket-Nachrichten
Das System sendet strukturierte JSON-Nachrichten mit Bestätigungsdaten:
```json
{
  "type": "cas_deposit_update",
  "data": {
    "id": 123,
    "current_confirmations": 5,
    "required_confirmations": 12,
    "status": "pending_confirmation",
    "deposit_tx_hash": "abc123..."
  }
}
```

### Status-Übergänge
- `pending` → `pending_confirmation` → `confirmed` → `completed`
- Das System verfolgt jeden Schritt und sendet Updates für jeden Statuswechsel 