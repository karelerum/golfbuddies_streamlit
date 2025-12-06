import altair as alt
import streamlit as st
import components.config as c
import components.psa_tables as t

def filter_verdi():

   # Finn rad med høyest turnerngsid (numerisk)
    valgt_default = c.VERDI.P6.value
    options = [v.value for v in c.VERDI]

    valgt_verdi = st.segmented_control(
        "Velg verdi",
        options=options,
        selection_mode="single",
        default=valgt_default,
        label_visibility="collapsed"
    )

    if not valgt_verdi:
        valgt_verdi = c.VERDI.P6.value

    return valgt_verdi

def dropdown_turnering():
    # --- 1️ Hent turneringsinfo og filtrer mot resultat ---
    df_turn = t.turneringsinfo()
    unique_ids = t.resultat()[c.TURNERINGSID].unique().tolist()
    df_turn = df_turn[df_turn[c.TURNERINGSID].isin(unique_ids)]

    # Finn rad med høyest turnerngsid (numerisk)
    valgt_default = df_turn.loc[df_turn[c.TURNERINGSID].idxmax(), "TurneringsNavn"]

    #  3. Dropdown for å velge turnering basert på navn
    options = df_turn["TurneringsNavn"].tolist()
    valgt_navn = st.selectbox(
        "Velg sesong:",
        options = options,
        index = options.index(valgt_default),
    )

    # 🔹 4. Finn valgt TurneringsId fra navn
    valgt_id = df_turn.loc[
        df_turn["TurneringsNavn"] == valgt_navn, c.TURNERINGSID
    ].iloc[0]  # første forekomst

    return valgt_id

def dropdown_runde(turneringsid):
    df = t.resultat()
    df = df[df[c.TURNERINGSID] == turneringsid]
    unique_ids = df[c.RUNDE_ID].unique().tolist()
        #  3. Dropdown for å velge turnering basert på navn
    options =  df["Runde"].unique().tolist()
    valgt_runde = st.selectbox(
        "Velg runde:",
        options = options,
        index = options.index(1),
    )
    return valgt_runde

def dropdown_runde_spillere(df_runde):
    df = df_runde
    df = df.drop(columns=["Hull"])
    options = [""] + df.columns.tolist()
    valgt_spiller = st.selectbox(
        "Velg spiller:",
        options = options,
        index = 0,
        placeholder="Velg spiller",
    )
    return valgt_spiller

def dropdown(valg_liste: list, tittel:str):
    valg_liste = list(dict.fromkeys(valg))

    valg = st.selectbox(
        tittel,
        options = valg_liste,
        index = valg_liste.index(1),
    )
    if not valg:
        valg = valg_liste[0]
    
    return valg


def line_chart(valgt_turneringsid: int ,valgt_verdi: str = c.VERDI.P6.value, akkumulert_ind: bool = False):

    df = t.resultat()
        #Filtrer på turneringsid
    df = df[df[c.TURNERINGSID].astype(int) == valgt_turneringsid]

    #Grupper til poeng pr runde
    df = df.groupby([c.ROUND, c.SPILLER])[valgt_verdi].sum().reset_index()
    #Rekkefølge spillere etter total poeng
    if valgt_verdi == c.VERDI.Slag.value:
        sort_value = True
        sort_line = "ascending"
    else:
        sort_value = False
        sort_line = "ascending"

   
    if akkumulert_ind: 
        df[valgt_verdi] = df.sort_values(["Spiller", "Runde"])\
                            .groupby("Spiller")[valgt_verdi].cumsum()

    spiller_rekkefoelge = df.groupby("Spiller")[valgt_verdi].sum().sort_values(ascending=sort_value).index.tolist()

        
    y_min = df[valgt_verdi].min() - (df[valgt_verdi].min() * 0.1)
    y_max = df[valgt_verdi].max() + (df[valgt_verdi].max() * 0.1)

    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Runde:O", title="Runde", sort="ascending", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                f"{valgt_verdi}:Q",
                title=valgt_verdi,
                scale=alt.Scale(domain=[y_min, y_max]),
                sort=sort_line,
            ),
            color=alt.Color(
                "Spiller:N",
                scale=alt.Scale(domain=spiller_rekkefoelge),
                legend=alt.Legend(
                    orient="top",    # ⬇️ plasser legend nederst
                    title=None          # Fjern tittel hvis ønskelig
                )
            ),
            tooltip=["Spiller", "Runde", valgt_verdi],
        )
        .interactive()
    )

    return chart


def input_spiller_passord(spiller_navn: str) -> bool:
    """Ber om passord for en spiller og returnerer True/False."""
    # Passordfelt
    passord_input = st.text_input(
        "Skriv inn passord:", 
        type="password",
        key=f"pwd_{spiller_navn}"
    )

    # Dersom bruker ikke har skrevet noe ennå
    if passord_input == "":
        return False

    # Sjekk mot riktig passord
    riktig_passord = c.PASSORD_MAP.get(spiller_navn)

    if riktig_passord is None:
        st.error("Denne spilleren har ikke et passord registrert.")
        return False

    if passord_input == riktig_passord:
        st.success("Passord godkjent! 🔓")
        return True
    else:
        st.error("Feil passord. Prøv igjen 🔐")
        return False

