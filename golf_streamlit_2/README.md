# GolfBuddies Streamlit

En enkel golf-score app bygget med Streamlit og Google Sheets som database.

## Datamodell i Google Sheets

- `runde_sheets_id`: ett ark per runde, navn = `rundeid` (f.eks. `20260101`)
- Scorekort-format per runde:
	- Kolonne A: `Hull`
	- Rader 2-19: `1..18`
	- Kolonner B..: én kolonne per spiller (`Spiller 1 .. Spiller x`)
- `General_Sheets_id`: ett ark per tabell (f.eks. `spillere`, `rundeinformasjon`, `baneinformasjon`)

## Kom i gang

1. Opprett virtuelt miljø og installer avhengigheter:

```bash
pip install -r requirements.txt
```

2. Legg inn secrets i `.streamlit/secrets.toml`:

```toml
[auth.passwords]
OleJ = "Nr1"

spreadsheet_id = "DIN_SHEET_ID"
service_account_file = ".streamlit/service_account.json"
scores_worksheet = "scores"

# Alternativt kan du bruke disse nøklene:
General_Sheets_id = "DIN_GENERAL_SHEET_ID"
runde_sheets_id = "DIN_RUNDE_SHEET_ID"
serviceaccount = "SERVICE_ACCOUNT_EMAIL"
```

3. Legg service account JSON i `.streamlit/service_account.json`.

Hvis du kjører i Cloud Run med Workload Identity/service account koblet til tjenesten,
kan appen bruke Application Default Credentials automatisk selv uten lokal JSON-fil.

4. Start appen:

```bash
streamlit run main.py
```

## MVP-sider

- Home
- Register Score
- Statistics

## Neste steg

- Legg til Players-side
- Legg til Leaderboard-side
- Flytt mer logikk til service-lag
- Legg til tester
