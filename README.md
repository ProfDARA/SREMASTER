# RESTUAJI INDUSTRIES SREMASTER

SRE Alert Brain adalah middleware yang menerima alert dari Grafana Cloud, mencari runbook yang sesuai, menjalankan reasoning opsional melalui Ollama, lalu membuat task di ClickUp.

## Alur sistem

```text
Grafana Cloud --POST /webhooks/grafana--> SRE Alert Brain --API--> ClickUp
                                               |
                                               +-- SQLite: alert dan runbook
                                               +-- Ollama: reasoning opsional
```

Alur webhook:

1. Grafana Cloud mengirim alert ke VM.
2. Service menyimpan event ke SQLite dan melakukan deduplication.
3. Label alert dicocokkan dengan database runbook.
4. Ollama melakukan enrichment jika diaktifkan.
5. Service membuat task pada ClickUp.
6. Event gagal dapat diproses ulang melalui endpoint retry.

## Fitur

- Webhook Grafana Cloud dengan shared secret.
- Penyimpanan alert dan runbook menggunakan SQLite.
- Pencocokan runbook berdasarkan label Grafana.
- Integrasi ClickUp API.
- Integrasi Ollama yang dapat diaktifkan atau dimatikan.
- Background processing agar webhook cepat mengembalikan respons `202`.
- Deduplication berdasarkan fingerprint alert.
- Endpoint retry untuk event yang gagal.
- Folder `runbooks/` untuk menyimpan runbook existing dalam format JSON.
- Docker dan Docker Compose.

## Menjalankan dengan Docker

Salin file konfigurasi:

```bash
cp .env.example .env
```

Isi minimal pada `.env`:

```env
WEBHOOK_SHARED_SECRET=ganti-dengan-secret-panjang
CLICKUP_API_TOKEN=pk_xxxxxxxxx
CLICKUP_LIST_ID=xxxxxxxxx
CLICKUP_DRY_RUN=false
OLLAMA_ENABLED=false
```

Jalankan service:

```bash
docker compose up -d --build
```

Periksa status:

```bash
curl http://localhost:8080/healthz
```

Respons yang diharapkan:

```json
{"status":"ok"}
```

## Konfigurasi Grafana Cloud

Buat Contact point dengan tipe Webhook dan gunakan URL berikut:

```text
https://<domain-atau-ip-vm>/webhooks/grafana
```

Tambahkan HTTP header berikut:

```text
X-Webhook-Secret: <nilai WEBHOOK_SHARED_SECRET>
```

Hubungkan Contact point tersebut ke Notification policy yang diperlukan. Endpoint publik sebaiknya menggunakan HTTPS melalui reverse proxy seperti Nginx, Caddy, atau load balancer.

## Konfigurasi ClickUp

Isi variabel berikut pada `.env`:

```env
CLICKUP_API_TOKEN=pk_xxxxxxxxx
CLICKUP_LIST_ID=xxxxxxxxx
```

Service akan membuat task melalui endpoint ClickUp berikut:

```text
POST https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task
```

Untuk pengujian tanpa membuat task sungguhan:

```env
CLICKUP_DRY_RUN=true
```

## Database dan file runbook

Simpan runbook existing di folder [`runbooks/`](runbooks/). Setiap file `*.json` akan dimuat otomatis ke SQLite ketika service start. Contoh tersedia di [`runbooks/api-high-error-rate.json`](runbooks/api-high-error-rate.json).

Format minimal:

```json
{
  "name": "High API error rate",
  "description": "Error rate API meningkat.",
  "match_labels": {"alertname": "APIHighErrorRate", "service": "payments"},
  "steps": ["Cek dashboard", "Periksa deployment terakhir"],
  "severity": "critical",
  "owner": "platform"
}
```

Jika folder diubah saat container sedang berjalan, reload dengan:

```bash
curl -X POST http://localhost:8080/api/runbooks/reload
```

`match_labels` menggunakan exact match dan case-sensitive. File dengan `name` dan `match_labels` yang sama akan diperbarui, bukan diduplikasi.

Runbook juga dapat ditambahkan melalui API:

Tambahkan runbook melalui API:

```bash
curl -X POST http://localhost:8080/api/runbooks \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"High API error rate",
    "description":"Respons API error meningkat.",
    "match_labels":{"alertname":"APIHighErrorRate","service":"payments"},
    "steps":["Cek dashboard API", "Periksa deployment terakhir", "Rollback bila diperlukan"],
    "severity":"critical",
    "owner":"platform"
  }'
```

`match_labels` menggunakan exact match dan case-sensitive. Runbook dengan jumlah label yang cocok paling banyak akan dipilih.

## Konfigurasi Ollama

Aktifkan reasoning layer dengan konfigurasi berikut:

```env
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT_SECONDS=45
```

Pastikan model telah tersedia:

```bash
ollama pull llama3.1:8b
```

Ollama hanya memperkaya task. Jika Ollama gagal, alert tetap diproses menggunakan rule dan runbook dasar.

## Endpoint API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/healthz` | Health check service |
| POST | `/webhooks/grafana` | Menerima alert Grafana |
| GET | `/api/runbooks` | Melihat runbook aktif |
| POST | `/api/runbooks` | Membuat runbook |
| POST | `/api/runbooks/reload` | Memuat ulang file JSON pada folder `runbooks/` |
| GET | `/api/events` | Melihat event terbaru |
| POST | `/api/events/{event_id}/retry` | Mengirim ulang event ke ClickUp |

## Pengujian webhook

```bash
curl -X POST http://localhost:8080/webhooks/grafana \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Secret: ganti-dengan-secret-panjang' \
  -d '{
    "receiver":"sre-clickup",
    "status":"firing",
    "groupKey":"test-api-alert",
    "commonLabels":{"severity":"critical","service":"payments"},
    "alerts":[{"status":"firing","labels":{"alertname":"APIHighErrorRate","service":"payments","severity":"critical"},"startsAt":"2026-09-30T10:00:00Z"}]
  }'
```

Periksa hasilnya:

```bash
curl http://localhost:8080/api/events
```

Status sukses adalah `delivered`. Pada mode dry-run, `clickup_task_id` bernilai `dry-run`.

## Troubleshooting

- `401 invalid webhook secret`: periksa nilai header dan `WEBHOOK_SHARED_SECRET`.
- Event `failed`: periksa field `error`, token ClickUp, List ID, dan log container.
- Grafana tidak dapat mengakses endpoint: periksa DNS, HTTPS, firewall, reverse proxy, dan port forwarding.
- Tidak ada runbook cocok: periksa nama serta value label karena matching exact.
- Ollama timeout: pastikan endpoint dapat dijangkau dari container dan model sudah tersedia.

Retry manual:

```bash
curl -X POST http://localhost:8080/api/events/<EVENT_ID>/retry
```

## Struktur proyek

```text
.
|-- app/
|   |-- config.py       # Environment configuration
|   |-- db.py           # SQLite schema and queries
|   |-- main.py         # FastAPI endpoints
|   `-- services.py     # Runbook, Ollama, and ClickUp logic
|-- docs/
|   |-- MANUAL_KONEKSI.md
|   `-- Manual-Koneksi-SRE-Alert-Brain.pdf
|-- runbooks/
|   |-- README.md
|   `-- api-high-error-rate.json
|-- Dockerfile
|-- docker-compose.yml
`-- requirements.txt
```

## Manual lengkap

- [Manual koneksi dalam Markdown](docs/MANUAL_KONEKSI.md)
- [Manual koneksi dalam PDF](docs/Manual-Koneksi-SRE-Alert-Brain.pdf)

## Catatan produksi

- Gunakan HTTPS dan secret webhook yang panjang.
- Jangan commit file `.env`.
- Batasi endpoint `/api/*` ke jaringan admin atau internal.
- Backup volume Docker yang berisi database SQLite.
- Monitor `/healthz` dan event dengan status `failed`.
- Pertimbangkan PostgreSQL dan queue worker jika volume alert sudah tinggi.
