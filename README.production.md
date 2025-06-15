# Cascoin-Polygon Bridge - Produktionsbereitstellung

## Übersicht
Diese Anleitung beschreibt die Bereitstellung der Cascoin-Polygon Bridge in einer Produktionsumgebung mit Docker und docker-compose.

## Voraussetzungen

### System-Anforderungen
- Docker Engine 20.10+
- Docker Compose 2.0+
- Mindestens 4GB RAM
- 50GB freier Speicherplatz
- Stabile Internetverbindung

### Blockchain-Knoten
- Funktionierender Cascoin-Knoten mit RPC-Zugang
- Polygon RPC-Endpunkt (Infura, Alchemy, oder eigener Knoten)
- Deployed wCAS Smart Contract auf Polygon

## Installation

### 1. Repository klonen
```bash
git clone <your-repository-url>
cd casserver
```

### 2. Umgebungsvariablen konfigurieren
```bash
# Kopieren Sie die Beispieldatei
cp env.production.example .env

# Bearbeiten Sie die .env Datei mit Ihren echten Werten
nano .env
```

**⚠️ WICHTIG:** Füllen Sie ALLE Variablen in der `.env` Datei aus, besonders:
- `MINTER_PRIVATE_KEY`: Private Key des Polygon-Minter-Accounts
- `INTERNAL_API_KEY`: Starker, eindeutiger API-Schlüssel
- `WCAS_CONTRACT_ADDRESS`: Adresse des deployed wCAS Contracts
- `POSTGRES_PASSWORD`: Sicheres Datenbankpasswort

### 3. Monitoring konfigurieren (optional)
```bash
# Erstellen Sie Monitoring-Verzeichnisse
mkdir -p monitoring/grafana/{datasources,dashboards}
mkdir -p monitoring

# Beispiel Prometheus-Konfiguration
cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'bridge-app'
    static_configs:
      - targets: ['bridge-app:8000']
EOF
```

### 4. Produktionsumgebung starten
```bash
# Alle Services starten
docker-compose -f docker-compose.prod.yml up -d

# Logs überwachen
docker-compose -f docker-compose.prod.yml logs -f bridge-app
```

## Services

### Haupt-Services
- **bridge-app**: Haupt-Bridge-Anwendung (Port 80, 8000)
- **postgres**: PostgreSQL Datenbank (Port 5432)
- **redis**: Redis Cache (Port 6379)

### Monitoring (optional)
- **prometheus**: Metriken-Sammlung (Port 9090)
- **grafana**: Monitoring-Dashboard (Port 3000)

## Überwachung

### Gesundheitschecks
```bash
# Status aller Services prüfen
docker-compose -f docker-compose.prod.yml ps

# Logs einsehen
docker-compose -f docker-compose.prod.yml logs bridge-app
docker-compose -f docker-compose.prod.yml logs postgres
```

### API-Endpunkte
- Haupt-Frontend: `http://your-server/`
- API-Dokumentation: `http://your-server:8000/docs`
- Gesundheitscheck: `http://your-server/health`

### Grafana (falls aktiviert)
- URL: `http://your-server:3000`
- Standard-Login: admin / (aus GRAFANA_ADMIN_PASSWORD)

## Wartung

### Backup
```bash
# Datenbank-Backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bridge_user cascoin_bridge > backup_$(date +%Y%m%d).sql

# Volumes-Backup
docker run --rm -v casserver_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup_$(date +%Y%m%d).tar.gz /data
```

### Updates
```bash
# Neue Version ziehen
git pull

# Services neu starten
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --build
```

### Logs rotieren
```bash
# Log-Rotation konfigurieren
sudo tee /etc/logrotate.d/docker-bridge << EOF
/var/lib/docker/containers/*/*.log {
  rotate 7
  daily
  compress
  size=1M
  missingok
  delaycompress
  copytruncate
}
EOF
```

## Sicherheit

### Firewall-Konfiguration
```bash
# Nur notwendige Ports öffnen
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (mit Reverse Proxy)
sudo ufw allow 22/tcp    # SSH (admin)

# Optional für Monitoring
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9090/tcp  # Prometheus
```

### SSL/TLS (empfohlen)
Verwenden Sie einen Reverse Proxy wie Nginx oder Traefik mit Let's Encrypt:

```bash
# Beispiel Nginx-Konfiguration
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Fehlerbehebung

### Häufige Probleme

1. **Bridge-App startet nicht**
   ```bash
   # Logs prüfen
   docker-compose -f docker-compose.prod.yml logs bridge-app
   
   # Umgebungsvariablen validieren
   docker-compose -f docker-compose.prod.yml config
   ```

2. **Datenbankverbindungsfehler**
   ```bash
   # PostgreSQL Status prüfen
   docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U bridge_user
   ```

3. **Blockchain-Verbindungsprobleme**
   ```bash
   # RPC-Verbindung testen
   curl -X POST -H "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":1}' \
        $POLYGON_RPC_URL
   ```

### Log-Analyse
```bash
# Fehler in Logs suchen
docker-compose -f docker-compose.prod.yml logs bridge-app | grep -i error

# Performance-Metriken
docker stats
```

## Performance-Optimierung

### Ressourcen-Limits setzen
Bearbeiten Sie `docker-compose.prod.yml`:
```yaml
services:
  bridge-app:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

### Datenbankoptimierung
```bash
# PostgreSQL-Konfiguration anpassen
docker-compose -f docker-compose.prod.yml exec postgres psql -U bridge_user -d cascoin_bridge -c "
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET max_connections = '100';
SELECT pg_reload_conf();
"
```

## Kontakt und Support

Bei Problemen oder Fragen:
1. Überprüfen Sie die Logs
2. Konsultieren Sie diese Dokumentation
3. Erstellen Sie ein Issue im Repository 