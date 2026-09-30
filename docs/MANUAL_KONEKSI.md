# Manual Koneksi RA INDUSTRIES SREMASTER Alert Brain

## 1. Gambaran alur

Grafana Cloud mengirim alert ke webhook pada VM. SRE Alert Brain menyimpan event, mencocokkan runbook, menjalankan analisis Ollama bila diaktifkan, lalu membuat task pada ClickUp.

```text
Grafana Cloud -> POST /webhooks/grafana -> SRE Alert Brain -> ClickUp
                                                   |
                                                   +-> SQLite runbook/event
                                                   +-> Ollama (opsional)
```

## 2. Prasyarat

- VM Linux/Windows yang dapat menerima koneksi HTTPS dari Grafana Cloud.
- Docker dan Docker Compose.
- Grafana Cloud dengan hak membuat Contact point dan Notification policy.
- ClickUp API token dan ID List tujuan.
- Ollama serta model yang sudah di-pull jika reasoning AI digunakan.

## 3. Deploy pada VM

Upload folder project ke VM, kemudian buat file environment.

```bash
cp .env.example .env
```

Isi `.env`:

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
docker compose logs -f sre-alert-brain
```

Tes health check dari VM:

```bash
curl http://localhost:8080/healthz
```

Respons yang benar:

```json
{"status":"ok"}
```

## 4. Konfigurasi ClickUp

1. Buka ClickUp dan tentukan List tujuan untuk incident SRE.
2. Ambil API token dari ClickUp Settings > Apps > API Token.
3. Ambil `List ID` dari URL List atau melalui ClickUp API.
4. Masukkan kedua nilai tersebut ke `.env`.
5. Restart service dengan `docker compose up -d`.

Task yang dibuat akan berisi nama alert, severity, label Grafana, waktu mulai, runbook, dan rekomendasi tindakan. Priority ClickUp dipetakan sebagai berikut: critical=1, high=2, warning=3, info=4.

Untuk uji tanpa membuat task sungguhan, gunakan:

```env
CLICKUP_DRY_RUN=true
```

## 5. Konfigurasi Grafana Cloud

1. Buka Grafana Cloud.
2. Masuk ke **Alerting > Contact points**.
3. Pilih **Add contact point**.
4. Pilih integration **Webhook**.
5. Isi URL:

```text
https://<domain-vm-anda>/webhooks/grafana
```

6. Tambahkan HTTP header:

```text
X-Webhook-Secret: <nilai WEBHOOK_SHARED_SECRET>
```

7. Simpan contact point.
8. Buka **Alerting > Notification policies** dan arahkan rule atau folder alert ke contact point tersebut.

URL harus HTTPS dan dapat diakses dari internet. Gunakan reverse proxy seperti Nginx, Caddy, atau load balancer untuk TLS. Port aplikasi internal default adalah `8080`.

## 6. Menambahkan database runbook

Runbook dapat dibuat melalui API. Contoh:

```bash
curl -X POST http://localhost:8080/api/runbooks \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"High API error rate",
    "description":"Error rate API melewati threshold.",
    "match_labels":{"alertname":"APIHighErrorRate","service":"payments"},
    "steps":[
      "Buka dashboard API payments",
      "Periksa deployment terakhir",
      "Periksa log aplikasi dan dependency",
      "Rollback bila insiden dimulai setelah deployment"
    ],
    "severity":"critical",
    "owner":"platform"
  }'
```

Matching menggunakan exact match pada label. Runbook dengan jumlah label cocok paling banyak akan dipilih.

## 7. Mengaktifkan Ollama

Jika Ollama berjalan pada VM yang sama:

```bash
ollama pull llama3.1:8b
ollama serve
```

Atur `.env`:

```env
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT_SECONDS=45
```

Jika Ollama berada di host atau server terpisah, ganti `OLLAMA_BASE_URL` dengan alamat yang dapat dijangkau container. Reasoning hanya memperkaya task; jika Ollama gagal, alert tetap diproses menggunakan runbook dan rule dasar.

## 8. Pengujian end-to-end

Kirim contoh alert dari VM:

```bash
curl -X POST http://localhost:8080/webhooks/grafana \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Secret: ganti-dengan-secret-panjang' \
  -d '{
    "receiver":"sre-clickup",
    "status":"firing",
    "groupKey":"test-api-alert",
    "commonLabels":{"severity":"critical","service":"payments"},
    "alerts":[{"status":"firing","labels":{"alertname":"APIHighErrorRate","service":"payments","severity":"critical"},"startsAt":"2026-09-30T10:00:00Z","annotations":{"summary":"API error rate tinggi"}}]
  }'
```

Periksa event:

```bash
curl http://localhost:8080/api/events
```

Status normal adalah `delivered`. Jika memakai dry-run, `clickup_task_id` akan bernilai `dry-run`.

## 9. Troubleshooting

**401 invalid webhook secret**: pastikan header `X-Webhook-Secret` sama persis dengan `WEBHOOK_SHARED_SECRET`.

**Event berstatus failed**: lihat field `error` pada `/api/events`, periksa token ClickUp, List ID, koneksi internet, dan log container.

**Grafana tidak dapat mengakses endpoint**: pastikan DNS publik, HTTPS valid, firewall, reverse proxy, dan port forwarding sudah benar.

**Tidak ada runbook yang cocok**: periksa label alert dan `match_labels`; matching bersifat exact dan case-sensitive.

**Ollama timeout**: pastikan model sudah tersedia, endpoint dapat dijangkau dari container, atau nonaktifkan `OLLAMA_ENABLED` sementara.

Untuk retry manual:

```bash
curl -X POST http://localhost:8080/api/events/<EVENT_ID>/retry
```

## 10. Checklist produksi

- Gunakan HTTPS dan secret webhook yang panjang.
- Jangan commit file `.env`.
- Batasi endpoint `/api/*` ke jaringan admin/internal.
- Backup volume Docker yang berisi database SQLite.
- Monitor `GET /healthz` dan status event failed.
- Pertimbangkan PostgreSQL dan queue worker jika volume alert sudah tinggi.
