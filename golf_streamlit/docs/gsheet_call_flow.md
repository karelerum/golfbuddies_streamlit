# Google Sheets Call Flow

This document shows the main call paths and why they happen.

## 1. App startup and bootstrap

```mermaid
flowchart TD
    A[main.py starts] --> B[ensure_sqlite_ready_for_session]
    B --> C{sqlite_bootstrap_checked?}
    C -- yes --> Z[skip bootstrap]
    C -- no --> D[ensure_sqlite_seeded_from_gsheet]
    D --> E[sqlite_needs_gsheet_bootstrap]
    E --> E1[get_latest_sqlite_audit_timestamp]
    E --> E2[get_latest_gsheet_change_timestamp]
    E2 --> E2a[get_latest_gsheet_audit_timestamp master]
    E2 --> E2b[get_latest_gsheet_audit_timestamp rounds]
    E --> E3[table_exists worksheet_list]
    E --> E4[get_table_row_count worksheet_list]
    E --> E5[list_sqlite_tables]
    E --> E6[_get_expected_sqlite_tables_from_gsheet]
    E6 --> E6a[list_worksheets master]
    E6 --> E6b[list_worksheets rounds]
    E -- no bootstrap needed --> Z
    E -- bootstrap needed --> F[sync_all_gsheets_to_sqlite]
```

### Why these calls happen

1. Hovedpunkt: Avgjør om bootstrap trengs.
Underpunkt: `get_latest_sqlite_audit_timestamp` sjekker om SQLite har synk-historikk.
Underpunkt: `get_latest_gsheet_change_timestamp` sjekker om Google Sheets er nyere enn SQLite.

2. Hovedpunkt: Verifiser at lokal speiling er komplett nok.
Underpunkt: `list_sqlite_tables`, `table_exists`, `get_table_row_count` sjekker lokal struktur.
Underpunkt: `list_worksheets` på master og rounds sjekker hvilke ark som finnes i Google Sheets.

3. Hovedpunkt: Start full synk hvis data er stale eller mangelfull.
Underpunkt: Hvis kontrollene over feiler eller viser avvik, kalles `sync_all_gsheets_to_sqlite`.

## 2. Full sync path

```mermaid
flowchart TD
    A[sync_all_gsheets_to_sqlite] --> B[sync_worksheet_list_to_sqlite]
    A --> C[sync_master_sheets_to_sqlite]
    A --> D[sync_rounds_sheets_to_sqlite]

    B --> B1[list_worksheets master]
    B --> B2[list_worksheets rounds]
    B --> B3[replace_sqlite_table_from_df worksheet_list]

    C --> C1[sync_sheets_to_sqlite master]
    D --> D1[sync_sheets_to_sqlite rounds]

    C1 --> C2[list_worksheets master]
    D1 --> D2[list_worksheets rounds]

    C1 --> C3[batch_sheets_to_dfs for all sheets in one/few calls]
    D1 --> D4[batch_sheets_to_dfs for all sheets in one/few calls]

    C1 --> C4[replace_sqlite_table_from_df each table]
    D1 --> D5[replace_sqlite_table_from_df each table]

    A --> E[ensure_gsheet_audit_baseline master]
    A --> F[ensure_gsheet_audit_baseline rounds]
```

### Why these calls happen

1. Hovedpunkt: Bygg metadataindeks over ark.
Underpunkt: `sync_worksheet_list_to_sqlite` lagrer kun liste over ark (ikke innhold).

2. Hovedpunkt: Synk faktisk innhold fra Google Sheets til SQLite.
Underpunkt: `sync_master_sheets_to_sqlite` og `sync_rounds_sheets_to_sqlite` orkestrerer hver sin kilde.
Underpunkt: `batch_sheets_to_dfs` henter alle ark i en kilde med `values.batchGet` i grupper på `BATCH_READ_CHUNK_SIZE` (15) ark per kall, i stedet for ett `sheet_to_df`-kall per ark.
Underpunkt: `replace_sqlite_table_from_df` skriver den leste DataFrame-en til riktig SQLite-tabell.

3. Hovedpunkt: Sikre audit-baseline for neste sammenligning.
Underpunkt: `ensure_gsheet_audit_baseline` sørger for at audit-grunnlaget finnes for senere diff-sjekk.

## 3. Saving a round from the UI

```mermaid
flowchart TD
    A[ui/pages/registrer_slag.py] --> B[save_round_and_sync]
    B --> C[_prepare_round_df]
    B --> D[_merge_edited_round_df]
    B --> E[_update_round_completion_status]
    B --> F[my_dfs.save_round_df]
    B --> G[my_dfs.save_round_info_df]
    B --> H[add_or_update_round_to_result]
    B --> I[badge_calc.calculate_achievements]
    B --> J[my_dfs.save_table_df spillermerker]
    B --> K[sync_df_to_gsheet round]
    B --> L[sync_df_to_gsheet round info]
    B --> M[sync_df_to_gsheet result]
    B --> N[sync_df_to_gsheet spillermerker]
```

### Why these calls happen

1. Hovedpunkt: Valider og bygg lagringsklar runde.
Underpunkt: Første blokk normaliserer input og merger endringer i forventet skjema.

2. Hovedpunkt: Lagre lokalt i SQLite først.
Underpunkt: SQLite er lokal source of truth i app-flyten.

3. Hovedpunkt: Oppdater avledede data.
Underpunkt: Resultat og achievements beregnes på nytt basert på siste lagrede runde.

4. Hovedpunkt: Speil tilbake til Google Sheets.
Underpunkt: Fire `sync_df_to_gsheet`-kall pusher round, round info, result og spillermerker.

## 4. Estimated Google Sheets call count

Dette er et praktisk estimat av antall Google Sheets-kall per flyt.

1. Startup check uten full bootstrap.
Underpunkt: Ca 4 read-kall som baseline.
Underpunkt: 2 kall fra `get_latest_gsheet_audit_timestamp` (master + rounds).
Underpunkt: 2 kall fra `list_worksheets` (master + rounds).

2. Full bootstrap/sync.
Underpunkt: Fast del: ca 6 read-kall.
Underpunkt: 2 kall i `sync_worksheet_list_to_sqlite` (`list_worksheets` master + rounds).
Underpunkt: 2 kall i `sync_master_sheets_to_sqlite`/`sync_rounds_sheets_to_sqlite` for worksheet-lister.
Underpunkt: Inntil 2 kall i `ensure_gsheet_audit_baseline` (master + rounds) for audit-kolonne-lesing.
Underpunkt: Variabel del: `ceil(N_master / 15) + ceil(N_rounds / 15)` read-kall fra `batch_sheets_to_dfs` (ett kall per 15 worksheets, i stedet for ett kall per worksheet).
Underpunkt: Total grovt: `6 + ceil(N_master / 15) + ceil(N_rounds / 15)` read-kall.

3. Lagring fra UI (`save_round_and_sync`).
Underpunkt: 4 write-kall til Google Sheets via `sync_df_to_gsheet`.
Underpunkt: Ekstra audit-kall skjer ved skriving (append til audit-log), men de er write-kall, ikke read-kall.

## 5. Where the quota pressure comes from

The quota pressure is mostly caused by read operations, not writes:

- startup bootstrap calls audit reads before the user even reaches the app
- full sync lists worksheets for master and rounds
- full sync reads each worksheet through `batch_sheets_to_dfs` (batched, but still one call per 15 sheets)
- audit-baseline checks may touch Google Sheets again after sync

In practice, the biggest repeat offenders are:

- `list_worksheets`
- `batch_sheets_to_dfs`
- `get_latest_gsheet_audit_timestamp`
- `ensure_gsheet_audit_baseline`

## 6. Improvement ideas

1. Cache bootstrap decisions per session.
Underpunkt: Appen markerer bootstrap i session state, men cold start treffer fortsatt flere sjekk-kall.

2. Keep audit-baseline best-effort.
Underpunkt: Audit er nyttig, men skal ikke blokkere appen ved quota.

3. Reduce repeated worksheet discovery.
Underpunkt: Lagre sist kjente worksheet-liste lokalt og refresh bare ved behov.

4. Split bootstrap into a lighter path.
Underpunkt: Kjør billig lokal sjekk først, og gå til Google Sheets kun når lokal state virker stale.

5. Make sync more explicit.
Underpunkt: Egen admin-knapp for "sync now" kan redusere automatisk startup-trafikk.

6. Avoid rereading the same sheet in one run.
Underpunkt: Neste steg er å sende videre allerede lastet worksheet-data i pipeline.

## 7. Short summary

- Startup decides whether SQLite needs a refresh.
- If yes, the app does a full Google Sheets -> SQLite sync.
- Round saving writes to SQLite first, then mirrors back to Google Sheets.
- Quota issues come from repeated reads, especially audit and worksheet discovery calls.
- The next wins are cheaper bootstrap checks and fewer reads during startup.
