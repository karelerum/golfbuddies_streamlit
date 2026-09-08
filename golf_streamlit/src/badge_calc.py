# Beregn badge og returner tildelte merker.

import pandas as pd

from .my_dfs import get_result_df, get_table_df


OUTPUT_COLUMNS = [
    'spiller',
    'rundeid',
    'turneringsid',
    'merke_id',
    'vinner_innen',
    'visningsnavn',
    'filnavn',
]

RESULT_SUM_COLUMNS = [
    'hole_in_one',
    'eagle',
    'birdie',
    'par_ind',
    'p6',
    'slag',
    'spiller_par',
    'other_ind',
]


def _assign_unique_placement(df, group_col):
    """Tildel entydig plassering per gruppe (1,2,3...) basert pa p6, slag og spiller."""
    sort_cols = [group_col, 'p6', 'slag', 'spiller']
    ascending = [True, False, True, True]
    ranked = df.sort_values(sort_cols, ascending=ascending).copy()
    ranked['plassering'] = ranked.groupby(group_col).cumcount() + 1
    return ranked


def _normalize_filter_token(value):
    """Normaliser filterverdi fra sheet (NA, tom, 1.0 -> 1)."""
    if pd.isna(value):
        return ''
    token = str(value).strip()
    if token == '' or token.lower() == 'nan':
        return ''
    if token.endswith('.0'):
        number_part = token[:-2]
        if number_part.isdigit():
            return number_part
    return token


def _get_merker_tildelt_df(
    df,
    df_merker_tildelt,
    kategori,
    verdi,
    vinner_innen,
    visningsnavn,
    filnavn,
    merke_id,
    kallenavn,
    eksklusiv_gruppe,
    prioritet,
    aar,
    delturnering,
):
    aar_filter = _normalize_filter_token(aar)
    delturnering_filter = _normalize_filter_token(delturnering)

    nye_rader = []
    for row_res in df.itertuples(index=False):
        rundeid = getattr(row_res, 'rundeid', pd.NA)
        turneringsid = getattr(row_res, 'turneringsid', pd.NA)
        birdie = getattr(row_res, 'birdie', 0)
        par_ind = getattr(row_res, 'par_ind', 0)
        other_ind = getattr(row_res, 'other_ind', 0)
        slag = getattr(row_res, 'slag', 0)
        spiller_par = getattr(row_res, 'spiller_par', pd.NA)
        plassering = getattr(row_res, 'plassering', pd.NA)
        turneringsid_str = '' if pd.isna(turneringsid) else str(turneringsid).strip()
        aar_value = turneringsid_str[:4]
        delturnering_value = turneringsid_str[5:6] if len(turneringsid_str) >= 6 else ''

        tildel = False

        if kategori == 'plassering' and pd.notna(plassering) and pd.notna(verdi):
            tildel = (
                plassering == verdi
                and (aar_filter == '' or aar_value == aar_filter)
                and (delturnering_filter == '' or delturnering_value == delturnering_filter)
            )

        elif kategori == 'antall_par' and pd.notna(verdi):
            tildel = par_ind >= verdi
        elif kategori == 'antall_birdie' and pd.notna(verdi):
            tildel = birdie >= verdi
        elif kategori == 'type_par' and pd.notna(verdi):
            tildel = spiller_par == verdi
        elif kategori == 'unik' and filnavn == 'hole_in_one.png':
            tildel = slag == 1
        elif kategori == 'unik' and filnavn == 'skogsmannen.png':
            tildel = other_ind >= 4

        if tildel:
            nye_rader.append(
                {
                    'spiller': kallenavn,
                    'rundeid': rundeid,
                    'turneringsid': turneringsid,
                    'merke_id': merke_id,
                    'vinner_innen': vinner_innen,
                    'visningsnavn': visningsnavn,
                    'filnavn': filnavn,
                    'eksklusiv_gruppe': eksklusiv_gruppe,
                    'prioritet': prioritet,
                }
            )

    if nye_rader:
        df_merker_tildelt = pd.concat([df_merker_tildelt, pd.DataFrame(nye_rader)], ignore_index=True)

    return df_merker_tildelt


def _apply_exclusive_group_rules(df_merker_tildelt):
    """Behold alle ikke-eksklusive merker, og kun hoyeste prioritet per spiller/scope/gruppe."""
    if df_merker_tildelt.empty:
        return df_merker_tildelt

    df = df_merker_tildelt.copy()
    df['eksklusiv_gruppe'] = df['eksklusiv_gruppe'].fillna('').astype(str)
    df['prioritet'] = pd.to_numeric(df['prioritet'], errors='coerce').fillna(0)

    df_merker_alltid = df[df['eksklusiv_gruppe'].eq('')]
    df_merker_eksklusiv = df[~df['eksklusiv_gruppe'].eq('')]

    if not df_merker_eksklusiv.empty:
        dedupe_frames = []

        df_runde = df_merker_eksklusiv[df_merker_eksklusiv['vinner_innen'].eq('runde')]
        if not df_runde.empty:
            dedupe_frames.append(
                df_runde
                .sort_values('prioritet')
                .drop_duplicates(
                    subset=['spiller', 'vinner_innen', 'eksklusiv_gruppe', 'rundeid'],
                    keep='last',
                )
            )

        df_turnering = df_merker_eksklusiv[df_merker_eksklusiv['vinner_innen'].eq('turnering')]
        if not df_turnering.empty:
            dedupe_frames.append(
                df_turnering
                .sort_values('prioritet')
                .drop_duplicates(
                    subset=['spiller', 'vinner_innen', 'eksklusiv_gruppe', 'turneringsid'],
                    keep='last',
                )
            )

        df_total_og_andre = df_merker_eksklusiv[
            ~df_merker_eksklusiv['vinner_innen'].isin(['runde', 'turnering'])
        ]
        if not df_total_og_andre.empty:
            dedupe_frames.append(
                df_total_og_andre
                .sort_values('prioritet')
                .drop_duplicates(
                    subset=['spiller', 'vinner_innen', 'eksklusiv_gruppe'],
                    keep='last',
                )
            )

        if dedupe_frames:
            df_merker_eksklusiv = pd.concat(dedupe_frames, ignore_index=True)
        else:
            df_merker_eksklusiv = df_merker_eksklusiv.iloc[0:0]

    return pd.concat([df_merker_alltid, df_merker_eksklusiv], ignore_index=True)


def calculate_achievements(df_spillere=None, df_resultater=None, df_merker=None):
    if df_spillere is None:
        df_spillere = get_table_df('spillere')
    if df_resultater is None:
        df_resultater = get_result_df()
    if df_merker is None:
        df_merker = get_table_df('merker')

    df_resultater = df_resultater.copy()
    df_merker = df_merker.copy()

    # Normaliser kolonnenavn for robust oppslag av filterfelter (f.eks. Aar/Delturnering).
    df_merker.columns = [str(column).strip().lower() for column in df_merker.columns]

    # Fyll inn turneringsid fra de 6 første tegnene i rundeid.
    if 'turneringsid' not in df_resultater.columns:
        df_resultater['turneringsid'] = df_resultater['rundeid'].astype(str).str[:6]
    else:
        mangler_turneringsid = (
            df_resultater['turneringsid'].isna()
            | df_resultater['turneringsid'].astype(str).str.strip().eq('')
        )
        if mangler_turneringsid.any():
            df_resultater.loc[mangler_turneringsid, 'turneringsid'] = (
                df_resultater.loc[mangler_turneringsid, 'rundeid'].astype(str).str[:6]
            )

    df_merker['kategori'] = df_merker['kategori'].fillna('').astype(str).str.strip().str.lower()
    df_merker['vinner_innen'] = df_merker['vinner_innen'].fillna('').astype(str).str.strip().str.lower()
    df_merker['vinner_innen'] = df_merker['vinner_innen'].replace({'totalt': 'total'})
    df_merker['verdi'] = pd.to_numeric(df_merker.get('verdi'), errors='coerce')

    for col in RESULT_SUM_COLUMNS:
        if col not in df_resultater.columns:
            df_resultater[col] = 0
        df_resultater[col] = pd.to_numeric(df_resultater[col], errors='coerce').fillna(0)

    df_resultat_round_grouped = (
        df_resultater
        .groupby(['rundeid', 'spiller'], as_index=False)
        .agg(
            **{column: (column, 'sum') for column in RESULT_SUM_COLUMNS},
            turneringsid=('turneringsid', 'max'),
        )
    )
    df_resultat_round_grouped = _assign_unique_placement(df_resultat_round_grouped, 'rundeid')

    df_resultat_turnering_grouped = (
        df_resultat_round_grouped
        .groupby(['turneringsid', 'spiller'], as_index=False)
        .agg(**{column: (column, 'sum') for column in RESULT_SUM_COLUMNS})
    )
    df_resultat_turnering_grouped = _assign_unique_placement(
        df_resultat_turnering_grouped,
        'turneringsid',
    )

    df_resultat_grouped = (
        df_resultat_round_grouped
        .groupby(['spiller'], as_index=False)
        .agg(**{column: (column, 'sum') for column in RESULT_SUM_COLUMNS})
    )
    df_resultat_grouped['rundeid'] = pd.NA
    df_resultat_grouped['turneringsid'] = pd.NA
    df_resultat_grouped['plassering'] = pd.NA

    alle_tildelinger = pd.DataFrame(
        columns=OUTPUT_COLUMNS + ['eksklusiv_gruppe', 'prioritet']
    )

    for kallenavn in df_spillere['Kallenavn'].dropna().astype(str):
        spiller_merker = pd.DataFrame(columns=OUTPUT_COLUMNS + ['eksklusiv_gruppe', 'prioritet'])

        spiller_res_pr_runde = df_resultat_round_grouped.loc[df_resultat_round_grouped['spiller'] == kallenavn]
        spiller_res_pr_turnering = df_resultat_turnering_grouped.loc[df_resultat_turnering_grouped['spiller'] == kallenavn]
        spiller_res_total = df_resultat_grouped.loc[df_resultat_grouped['spiller'] == kallenavn]

        for row in df_merker.itertuples(index=False):
            kategori = str(getattr(row, 'kategori', '')).strip().lower()
            verdi = getattr(row, 'verdi', pd.NA)
            vinner_innen = str(getattr(row, 'vinner_innen', '')).strip().lower()
            visningsnavn = getattr(row, 'visningsnavn', '')
            filnavn = getattr(row, 'filnavn', '')
            merke_id = getattr(row, 'merke_id', pd.NA)
            eksklusiv_gruppe = getattr(row, 'eksklusiv_gruppe', '')
            prioritet = getattr(row, 'prioritet', pd.NA)
            aar = getattr(row, 'aar', pd.NA)
            delturnering = getattr(row, 'delturnering', getattr(row, 'delturneri', pd.NA))

            if vinner_innen == 'runde':
                scope_df = spiller_res_pr_runde
                aar = None  # Ikke relevant for runde-merker
            elif vinner_innen == 'turnering':
                scope_df = spiller_res_pr_turnering
            elif vinner_innen == 'total':
                scope_df = spiller_res_total
                aar = None  # Ikke relevant for total-merker
                delturnering = None
                
            else:
                continue

            spiller_merker = _get_merker_tildelt_df(
                scope_df,
                spiller_merker,
                kategori,
                verdi,
                vinner_innen,
                visningsnavn,
                filnavn,
                merke_id,
                kallenavn,
                eksklusiv_gruppe,
                prioritet,
                aar,
                delturnering,
            )

        if not spiller_merker.empty:
            alle_tildelinger = pd.concat([alle_tildelinger, spiller_merker], ignore_index=True)

    if alle_tildelinger.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    alle_tildelinger = _apply_exclusive_group_rules(alle_tildelinger)

    alle_tildelinger = alle_tildelinger.drop_duplicates(
        subset=['spiller', 'rundeid', 'turneringsid', 'merke_id', 'vinner_innen', 'visningsnavn', 'filnavn']
    )
    alle_tildelinger = alle_tildelinger.sort_values(['spiller', 'vinner_innen', 'merke_id']).reset_index(drop=True)
    return alle_tildelinger[OUTPUT_COLUMNS]



