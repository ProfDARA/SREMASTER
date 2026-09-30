# Runbook existing

Simpan runbook existing sebagai file `*.json` di folder ini. Semua file akan dimuat ke SQLite ketika service start. Untuk memuat perubahan tanpa restart:

```bash
curl -X POST http://localhost:8080/api/runbooks/reload
```

Format file:

```json
{
  "name": "Nama runbook",
  "description": "Kapan runbook ini digunakan.",
  "match_labels": {
    "alertname": "NamaAlert",
    "service": "nama-service"
  },
  "steps": [
    "Cek dashboard terkait",
    "Periksa log dan deployment terakhir"
  ],
  "severity": "critical",
  "owner": "platform"
}
```

`match_labels` menggunakan exact match dan case-sensitive. File yang memiliki nama dan `match_labels` sama akan di-update, bukan diduplikasi.
