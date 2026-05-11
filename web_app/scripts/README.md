# Tikpan web_app database portability

The live SQLite database in `web_app/data/tikpan.db` is local runtime state and is intentionally ignored by Git. Use these scripts to move reusable business configuration between computers without committing user balances, orders, logs, password hashes, or API keys.

## Initialize a new computer

```powershell
python web_app/scripts/init_db.py
```

This creates the schema and imports `web_app/data/seed.example.json`.

## Export portable configuration

```powershell
python web_app/scripts/export_config.py --out web_app/data/config.export.json
```

The default export includes:

- model categories
- web model definitions
- model form fields
- pricing and billing rules
- provider channels, with API keys redacted
- model provider routes
- non-sensitive system settings

It does not export users, orders, balances, generation logs, agent private data, password hashes, or recovery records.

## Import on another computer

```powershell
python web_app/scripts/import_config.py --in web_app/data/config.export.json
```

Imports are idempotent. Existing provider API keys are preserved when the imported file has a blank redacted key.

## Private local backup

For a private machine-to-machine move, you can include secrets:

```powershell
python web_app/scripts/export_config.py --include-secrets --out web_app/data/config.backup.json
```

Files matching `web_app/data/*.export.json`, `web_app/data/*.backup.json`, and `web_app/data/config.local.json` are ignored by Git. Keep private backups out of public repositories.
