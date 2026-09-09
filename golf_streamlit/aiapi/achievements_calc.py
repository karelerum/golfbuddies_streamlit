from __future__ import annotations

import pandas as pd


def build_default_badge_catalog() -> pd.DataFrame:
    rows = [
        {"kategori": "unik", "verdi": None, "vinner_innen": "totalt", "visningsnavn": "Hole in one", "filnavn": "hole_in_one.png", "b": 1},
        {"kategori": "type_par", "verdi": -2, "vinner_innen": "totalt", "visningsnavn": "Eagle", "filnavn": "eagle.png", "b": 3},
        {"kategori": "antall_par", "verdi": 5, "vinner_innen": "runde", "visningsnavn": "5 Par", "filnavn": "5_par.png", "b": 20},
        {"kategori": "antall_par", "verdi": 10, "vinner_innen": "runde", "visningsnavn": "10 Par", "filnavn": "10_par.png", "b": 10},
        {"kategori": "unik", "verdi": None, "vinner_innen": "runde", "visningsnavn": "Skogsmannen", "filnavn": "skogsmannen.png", "b": 99},
        {"kategori": "antall_birdie", "verdi": 1, "vinner_innen": "runde", "visningsnavn": "Birdie", "filnavn": "1_birdie.png", "b": 30},
        {"kategori": "antall_birdie", "verdi": 3, "vinner_innen": "runde", "visningsnavn": "3 Birdies", "filnavn": "3_birdie.png", "b": 15},
        {"kategori": "antall_birdie", "verdi": 5, "vinner_innen": "runde", "visningsnavn": "5 Birdies", "filnavn": "5_birdie.png", "b": 11},
        {"kategori": "antall_birdie", "verdi": 1, "vinner_innen": "totalt", "visningsnavn": "Baby Birdie", "filnavn": "baby_birbie.png", "b": 50},
        {"kategori": "antall_birdie", "verdi": 5, "vinner_innen": "totalt", "visningsnavn": "Young Birdie", "filnavn": "young_birdie.png", "b": 40},
        {"kategori": "antall_birdie", "verdi": 20, "vinner_innen": "totalt", "visningsnavn": "Birdie Pro", "filnavn": "birdie_pro.png", "b": 9},
        {"kategori": "antall_birdie", "verdi": 50, "vinner_innen": "totalt", "visningsnavn": "Birdie Beast", "filnavn": "birdie_beast.png", "b": 5},
        {"kategori": "antall_birdie", "verdi": 100, "vinner_innen": "totalt", "visningsnavn": "Legendary Birdie", "filnavn": "legendary_birdie.png", "b": 4},
        {"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "visningsnavn": "Rundens vinner", "filnavn": "rundens_vinner.png", "b": None},
        {"kategori": "plassering", "verdi": 2, "vinner_innen": "runde", "visningsnavn": "Rundens nr 2", "filnavn": "rundens_nr2.png", "b": None},
        {"kategori": "plassering", "verdi": 3, "vinner_innen": "runde", "visningsnavn": "Rundens nr 3", "filnavn": "rundens_nr3.png", "b": None},
        {"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "visningsnavn": "Vinter Rundens Vinner", "filnavn": "rundens_vinner.png", "b": None},
        {"kategori": "plassering", "verdi": 2, "vinner_innen": "runde", "visningsnavn": "Vinter Rundens nr 2", "filnavn": "rundens_nr2.png", "b": None},
        {"kategori": "plassering", "verdi": 3, "vinner_innen": "runde", "visningsnavn": "Vinter Rundens nr 3", "filnavn": "rundens_nr3.png", "b": None},
        {"kategori": "plassering", "verdi": 1, "vinner_innen": "turnering", "visningsnavn": "Vinner VO 2024", "filnavn": "vinner_vo_2024.png", "b": None},
        {"kategori": "plassering", "verdi": 2, "vinner_innen": "turnering", "visningsnavn": "Vinner VO 2025", "filnavn": "vinner_vo_2025.png", "b": None},
        {"kategori": "plassering", "verdi": 3, "vinner_innen": "turnering", "visningsnavn": "Vinner VO 2026", "filnavn": "vinner_vo_2026.png", "b": None},
        {"kategori": "plassering", "verdi": 1, "vinner_innen": "turnering", "visningsnavn": "Vinner VO Vinter 24/25", "filnavn": "vinner_vo_vinter_2024.png", "b": None},
        {"kategori": "plassering", "verdi": 2, "vinner_innen": "turnering", "visningsnavn": "Vinner VO Vinter 25/26", "filnavn": "vinner_vo_vinter_2025.png", "b": None},
        {"kategori": "plassering", "verdi": 3, "vinner_innen": "turnering", "visningsnavn": "Vinner VO Vinter 26/27", "filnavn": "vinner_vo_vinter_2026.png", "b": None},
    ]
    return pd.DataFrame(rows)


def calculate_achievements(
    result_df: pd.DataFrame | None,
    round_info_df: pd.DataFrame | None,
    tournament_df: pd.DataFrame | None = None,
    badge_catalog_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if result_df is None or result_df.empty:
        return pd.DataFrame(columns=["spiller", "merkeid", "vinner_innen_totalt"])
    if round_info_df is None or round_info_df.empty:
        raise ValueError("rundeinfo mangler og trengs for achievements-beregning")

    catalog_df = badge_catalog_df.copy() if badge_catalog_df is not None else build_default_badge_catalog()
    rules_df = _normalize_badge_rules_df(catalog_df)
    merged_df = _prepare_result_context(result_df, round_info_df, tournament_df)
    if merged_df.empty or rules_df.empty:
        return pd.DataFrame(columns=["spiller", "merkeid", "vinner_innen_totalt"])

    scope_config = {
        "runde": {"group_cols": ["rundeid", "spiller"], "parent_cols": ["rundeid"]},
        "turnering": {"group_cols": ["turneringsid", "spiller"], "parent_cols": ["turneringsid"]},
        "totalt": {"group_cols": ["spiller"], "parent_cols": []},
    }

    def add_rows(players: list[str], merkeid: str, scope: str) -> list[dict[str, str]]:
        return [
            {
                "spiller": str(spiller),
                "merkeid": str(merkeid),
                "vinner_innen_totalt": scope,
            }
            for spiller in players
        ]

    awarded_rows: list[dict[str, str]] = []

    # antall_birdie / antall_par: choose highest threshold hit per scope-group.
    for kategori, value_column in [("antall_birdie", "birdie"), ("antall_par", "par_ind")]:
        category_rules = rules_df.loc[(rules_df["kategori"] == kategori) & (rules_df["verdi"].notna())].copy()
        for scope, cfg in scope_config.items():
            scoped_rules = category_rules.loc[category_rules["vinner_innen_totalt"] == scope].copy()
            if scoped_rules.empty:
                continue
            scoped_rules = scoped_rules.sort_values("verdi", ascending=False)

            counts_df = merged_df.groupby(cfg["group_cols"], as_index=False)[value_column].sum()
            if counts_df.empty:
                continue

            for _, grouped_row in counts_df.iterrows():
                hits = float(grouped_row[value_column])
                matching = scoped_rules.loc[scoped_rules["verdi"] <= hits].head(1)
                if matching.empty:
                    continue
                rule = matching.iloc[0]
                awarded_rows.extend(add_rows([str(grouped_row["spiller"])], str(rule["merkeid"]), scope))

    # type_par: count of spiller_par == -2.
    type_rules = rules_df.loc[rules_df["kategori"] == "type_par"].copy()
    for _, rule in type_rules.iterrows():
        scope = str(rule["vinner_innen_totalt"])
        cfg = scope_config.get(scope)
        if cfg is None:
            continue
        threshold = int(rule["verdi"]) if pd.notna(rule["verdi"]) else 1
        counts_df = merged_df.groupby(cfg["group_cols"], as_index=False)["is_type_par_minus2"].sum()
        winners = counts_df.loc[counts_df["is_type_par_minus2"] >= threshold, "spiller"].astype(str).tolist()
        awarded_rows.extend(add_rows(winners, str(rule["merkeid"]), scope))

    # plassering: rank by p6 within scope parent, and award exact placement (verdi).
    place_rules = rules_df.loc[(rules_df["kategori"] == "plassering") & (rules_df["verdi"].notna())].copy()
    vinter_round_ids = set(
        merged_df.loc[merged_df["type"].str.strip().str.lower().eq("vinter"), "rundeid"].astype(str).unique().tolist()
    )
    tournament_name_df = merged_df[["turneringsid", "turneringsnavn"]].drop_duplicates(subset=["turneringsid"])

    for scope, cfg in scope_config.items():
        scoped_rules = place_rules.loc[place_rules["vinner_innen_totalt"] == scope].copy()
        if scoped_rules.empty:
            continue

        totals_df = merged_df.groupby(cfg["group_cols"], as_index=False)["p6"].sum()
        if totals_df.empty:
            continue

        if cfg["parent_cols"]:
            totals_df["plassering"] = totals_df.groupby(cfg["parent_cols"])["p6"].rank(method="min", ascending=False).astype("Int64")
        else:
            totals_df["plassering"] = totals_df["p6"].rank(method="min", ascending=False).astype("Int64")

        if scope == "turnering" and "turneringsid" in totals_df.columns:
            totals_df = totals_df.merge(tournament_name_df, on="turneringsid", how="left")
            totals_df["turneringsnavn"] = totals_df["turneringsnavn"].fillna("").astype(str)

        for _, rule in scoped_rules.iterrows():
            wanted = int(rule["verdi"])
            candidates = totals_df.loc[totals_df["plassering"] == wanted].copy()

            if scope == "runde" and "vinter" in str(rule["visningsnavn"]).strip().lower():
                candidates = candidates.loc[candidates["rundeid"].astype(str).isin(vinter_round_ids)]

            if scope == "turnering":
                target = _extract_tournament_name_target(str(rule["visningsnavn"]))
                if target:
                    candidates = candidates.loc[
                        candidates["turneringsnavn"].map(_normalize_text).str.contains(target, na=False)
                    ]

            winners = candidates["spiller"].astype(str).tolist()
            awarded_rows.extend(add_rows(winners, str(rule["merkeid"]), scope))

    # unik rules.
    unik_rules = rules_df.loc[rules_df["kategori"] == "unik"].copy()
    for _, rule in unik_rules.iterrows():
        scope = str(rule["vinner_innen_totalt"])
        cfg = scope_config.get(scope)
        if cfg is None:
            continue

        name = str(rule["visningsnavn"]).strip().lower()
        if "hole in one" in name:
            rule_column, threshold = "is_hole_in_one", 1
        elif "skogsmannen" in name:
            rule_column, threshold = "is_skogsmannen_hit", 5
        else:
            continue

        counts_df = merged_df.groupby(cfg["group_cols"], as_index=False)[rule_column].sum()
        winners = counts_df.loc[counts_df[rule_column] >= threshold, "spiller"].astype(str).tolist()
        awarded_rows.extend(add_rows(winners, str(rule["merkeid"]), scope))

    if not awarded_rows:
        return pd.DataFrame(columns=["spiller", "merkeid", "vinner_innen_totalt"])

    awarded_df = pd.DataFrame(awarded_rows)
    awarded_df = awarded_df.drop_duplicates(subset=["spiller", "merkeid", "vinner_innen_totalt"])
    awarded_df = awarded_df.sort_values(["spiller", "merkeid", "vinner_innen_totalt"]).reset_index(drop=True)
    return awarded_df


def _normalize_badge_rules_df(catalog_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"kategori", "vinner_innen", "visningsnavn", "filnavn"}
    missing = required_columns.difference(catalog_df.columns)
    if missing:
        missing_display = ", ".join(sorted(missing))
        raise ValueError(f"badge-katalog mangler kolonner: {missing_display}")

    df = catalog_df.copy()
    if "b" not in df.columns:
        df["b"] = pd.NA
    if "verdi" not in df.columns:
        df["verdi"] = pd.NA

    df["kategori"] = df["kategori"].fillna("").astype(str).str.strip().str.lower()
    df["vinner_innen_totalt"] = df["vinner_innen"].fillna("").astype(str).str.strip().str.lower()
    df["visningsnavn"] = df["visningsnavn"].fillna("").astype(str).str.strip()
    df["filnavn"] = df["filnavn"].fillna("").astype(str).str.strip()
    df["verdi"] = pd.to_numeric(df["verdi"], errors="coerce").astype("Int64")
    df["merkeid"] = df.apply(_resolve_merkeid, axis=1)
    return df


def _prepare_result_context(
    result_df: pd.DataFrame,
    round_info_df: pd.DataFrame,
    tournament_df: pd.DataFrame | None,
) -> pd.DataFrame:
    df = result_df.copy()
    df["rundeid"] = df["rundeid"].astype(str)
    df["spiller"] = df["spiller"].astype(str)

    for column in ["birdie", "par_ind", "p6", "slag", "par", "spiller_par", "hole_in_one"]:
        if column not in df.columns:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    # Ensure condition columns can be computed even when source indicators are missing.
    df["is_hole_in_one"] = (
        (pd.to_numeric(df["slag"], errors="coerce").fillna(0) == 1)
        | (pd.to_numeric(df["hole_in_one"], errors="coerce").fillna(0) > 0)
    ).astype(int)
    if "spiller_par" not in result_df.columns:
        df["spiller_par"] = pd.to_numeric(df["slag"], errors="coerce").fillna(0) - pd.to_numeric(df["par"], errors="coerce").fillna(0)
    df["is_type_par_minus2"] = (pd.to_numeric(df["spiller_par"], errors="coerce").fillna(0) == -2).astype(int)
    df["is_skogsmannen_hit"] = (pd.to_numeric(df["spiller_par"], errors="coerce").fillna(0) > 4).astype(int)

    info_df = round_info_df[["rundeid", "turneringsid", "runde", "ferdig_ind"]].copy()
    info_df["rundeid"] = info_df["rundeid"].astype(str)
    info_df["turneringsid"] = info_df["turneringsid"].astype(str)
    info_df["ferdig_ind"] = pd.to_numeric(info_df["ferdig_ind"], errors="coerce").fillna(0).astype(int)

    merged_df = df.merge(info_df, on="rundeid", how="left")
    merged_df = merged_df.loc[merged_df["ferdig_ind"] == 1].copy()

    if tournament_df is not None and not tournament_df.empty and "turneringsid" in tournament_df.columns:
        tournament_meta_df = tournament_df[[col for col in ["turneringsid", "turneringsnavn", "type"] if col in tournament_df.columns]].copy()
        tournament_meta_df["turneringsid"] = tournament_meta_df["turneringsid"].astype(str)
        if "turneringsnavn" not in tournament_meta_df.columns:
            tournament_meta_df["turneringsnavn"] = ""
        if "type" not in tournament_meta_df.columns:
            tournament_meta_df["type"] = ""
        tournament_meta_df["turneringsnavn"] = tournament_meta_df["turneringsnavn"].fillna("").astype(str)
        tournament_meta_df["type"] = tournament_meta_df["type"].fillna("").astype(str)
        merged_df = merged_df.merge(tournament_meta_df, on="turneringsid", how="left")
    else:
        merged_df["turneringsnavn"] = ""
        merged_df["type"] = ""

    merged_df["turneringsnavn"] = merged_df["turneringsnavn"].fillna("").astype(str)
    merged_df["type"] = merged_df["type"].fillna("").astype(str)
    return merged_df


def _resolve_merkeid(row: pd.Series) -> str:
    badge_id = row.get("b")
    if pd.notna(badge_id) and str(badge_id).strip() != "":
        badge_num = pd.to_numeric(badge_id, errors="coerce")
        if pd.notna(badge_num):
            return str(int(badge_num))
        return str(badge_id).strip()

    filename = str(row.get("filnavn") or "").strip()
    if filename:
        return filename.rsplit(".", 1)[0].lower()
    return str(row.get("visningsnavn") or "ukjent").strip().lower().replace(" ", "_")


def _extract_tournament_name_target(display_name: str) -> str:
    normalized_name = display_name.strip()
    if normalized_name.lower().startswith("vinner "):
        normalized_name = normalized_name[7:]
    return _normalize_text(normalized_name)


def _normalize_text(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())
