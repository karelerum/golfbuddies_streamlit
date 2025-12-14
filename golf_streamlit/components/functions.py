import pandas as pd
import components.config as c
import streamlit as st
import time

def add_best_slag_col(df: pd.DataFrame) -> pd.DataFrame:
    return pd

def add_6p_syst_col(df: pd.DataFrame) -> pd.DataFrame:
        # Rens kolonnenavn for evt. whitespace
    df = df.rename(columns=lambda c: c.strip())
    base_points = {
        1: 6,
        2: 5,
        3: 4,
        4: 3,
        5: 2,
        6: 1,
        # 7+ -> 0
    }

    group_cols = ["TurneringsId", "Runde", "Hull"]

    def _score_one_group(g: pd.DataFrame) -> pd.DataFrame:
        # --- behold group info slik at include_groups=False fungerer ---
        group_info = dict(zip(group_cols, g.name))

        g = g.copy()

        # Færrest slag er best → ascending=True
        g["rank_min"] = g["Slag"].rank(
            method="min",
            ascending=True,
        ).astype(int)

        # Hvor mange deler dette antall slag?
        g["tie_size"] = g.groupby("Slag")["Slag"].transform("size")

        def calc_row_points(row):
            start = row["rank_min"]
            size = row["tie_size"]

            # Alle plasser som deles, f.eks. 3 og 4 -> [3, 4]
            positions = range(start, start + size)

            pts = [base_points.get(pos, 0) for pos in positions]
            return sum(pts) / len(pts) if pts else 0.0

        g[c.COL_POINTS_6] = g.apply(calc_row_points, axis=1)

        # Fjern hjelpekolonner
        out = g.drop(columns=["rank_min", "tie_size"])

        # --- legg group-kolonnene tilbake ---
        for col, val in group_info.items():
            out[col] = val

        return out
    df_scored = (
        df
        .groupby(group_cols, group_keys=False)
        .apply(_score_one_group, include_groups=False)
    )

    return df_scored

def add_1p_syst_col(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    min_slag_per_hull = (
        df.groupby(["TurneringsId", "Runde", "Hull"])["Slag"]
        .transform("min")
    )

    is_best = df["Slag"].eq(min_slag_per_hull)

    best_count_per_hull = (
        is_best
        .groupby([df["TurneringsId"], df["Runde"], df["Hull"]])
        .transform("sum")
    )

    df["1-poeng-syst"] = 0.0
    df.loc[is_best, "1-poeng-syst"] = 1.0 / best_count_per_hull[is_best]

    return df

def add_beste_slag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["beste_slag"] = (
        df.groupby(["TurneringsId", "Runde", "Hull"])["Slag"]
        .transform("min")
    )

    return df


def rundeid_til_filnavn(rundeid: int | str) -> str:
    r = str(rundeid).zfill(8)   # sikre 8 siffer

    turneringsid = r[:6]        # første 6 siffer
    runde = r[6:]               # siste 2 siffer

    return f"Runde_{turneringsid}_{runde}"

#formatering_styled_number
def fmt(x):
    # Hopp over None / NaN
    if pd.isna(x):
        return ""
    # Hvis tallet er heltall (5.0, 7.0, 0.0)
    if float(x).is_integer():
        return str(int(x))
    # Finn faktisk antall desimaler i råverdien
    raw = str(x).rstrip("0")  # fjerner unødvendige nuller
    if "." in raw:
        decimals = len(raw.split(".")[1])
    else:
        decimals = 0
    if decimals == 1:
        return f"{x:.1f}"
    # Ellers vis med 1 desimal
    return f"{x:.2f}"

def finn_spiller_for_passord(pwd: str) -> str | None:
    """Returnerer spillernavn for gitt passord, eller None hvis ingen match."""
    for spiller, spiller_pwd in c.PASSORD_MAP.items():
        if pwd == spiller_pwd:
            return spiller
    return None


def sjekk_spiller_passord() -> bool:
    """
    Viser passord-boks og setter global innlogging:
      - st.session_state["passord_ok_ind"] = True/False
      - st.session_state["innlogget_spiller"] = spillernavn
    Returnerer True hvis innlogging er ok, ellers False.
    """

    # Allerede logget inn i denne sesjonen?
    if st.session_state.get("passord_ok_ind", False):
        return True

    st.markdown("### Passord")
    pwd = st.text_input("Skriv inn passord for å åpne appen:", type="password")

    #if pwd == "":
        # Ikke skrevet noe enda → ikke vis feilmelding, bare vent
     #   return False

    if not st.button("Logg inn", type="primary"):
        st.stop() 
    
    spiller = finn_spiller_for_passord(pwd)

    if spiller is None:
        st.error("Feil passord. Prøv igjen 🔐")
        return False

    # Passord er ok → lagre globalt
    st.session_state["passord_ok_ind"] = True
    st.session_state["innlogget_spiller"] = spiller
    st.success(f"Passord godkjent! 🔓")
    with st.spinner("Logger inn…"):
        time.sleep(1)
    st.rerun() 
    
    return True

def button_nav(label: str) -> None:
    """Navigasjonsknapp som setter valgt side i session_state."""
    label,
    on_click=lambda: st.session_state.update(valgt_side=label),
    type="primary" if st.session_state.valgt_side == label else "secondary",
    use_container_width=True
