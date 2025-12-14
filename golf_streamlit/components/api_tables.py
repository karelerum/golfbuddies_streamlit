import components.config as c
import components.psa_tables as t
import streamlit as st
import components.functions as f

def resultat_runde_pivot(turneringsid: int, valgt_verdi: str):
    #Hent data
    df = t.resultat()

    #Filtrer på turneringsid
    df = df[df[c.TURNERINGSID].astype(int) == turneringsid]

    
    #Grupper til poeng pr runde
    df = df.groupby([c.ROUND, c.SPILLER])[valgt_verdi].sum().reset_index()

    df[valgt_verdi] = df[valgt_verdi].round(2)
    #Pivoter til Visning
    df = df.pivot(index = c.SPILLER, columns=c.ROUND , values=valgt_verdi)
    #Legg på totalt
    df["Total"] = df.select_dtypes(include="number").sum(axis=1)

    if valgt_verdi == c.VERDI.Slag.value:
        sort_value = True
    else: sort_value = False
        
    df = df.sort_values(by="Total", ascending=sort_value)

    return df

def resultat_pr_hull(turneringsid, valgt_runde:int, valgt_verdi: str):
    df = t.resultat()
    df = df[df[c.TURNERINGSID].astype(int) == turneringsid]
    df = df[df["Runde"].astype(int) == valgt_runde]

    pivot = df.pivot_table(
        index="Hull",
        columns="Spiller",
        values=valgt_verdi,
        aggfunc="first"    # én verdi per hull + spiller
    )

    pivot.index.name = None

    # Highlight-funksjon: marker høyeste verdier i hver rad
    def highlight(s):
        if valgt_verdi == c.VERDI.Slag.value:
            is_value = s == s.min()
        else: is_value = s == s.max()
    
        return [
            "font-weight: 700; background-color: rgba(255, 65, 65, 0.20);"
            if v else ""
            for v in is_value
        ]
    pivot = f.move_spiller_first(pivot)   
    # Returnér en styler
    pivot = (
        pivot.style
        .apply(highlight, axis=1)
        .format(f.fmt) 
    )
    return pivot


def resultat_annet_goy_eagle_osv(turneringsid):
    df = t.resultat()
    df = df[df[c.TURNERINGSID].astype(int) == turneringsid]
    df_pre_sum = df[[
        "Spiller",
        "Hole in one",
        "Eagle",
        "Birdie",
        "Par_ind",
        "Bogey",
        "2 Bogey",
        "3 Bogey",
        "Other"
    ]]
    df_sum = df_pre_sum.groupby("Spiller", as_index=False).sum()
    df_sum = df_sum.loc[:, (df_sum != 0).any(axis=0)] #Fjern kolonner som bare inneholder 0
    df_sum = df_sum.rename(columns={"Par_ind": "Par"})
    return df_sum

def resultat_goy_gruppen_runde(turneringsid):
    df = t.resultat()
    df = df[df[c.TURNERINGSID].astype(int) == turneringsid]
    df = df[df["Spiller"] == "OleJ"]
    df["beste_par"] = df["Beste_slag"].astype(int) - df["Par"].astype(int)
    df_sum = (
        df
        .groupby("Runde", as_index=False)
        .agg(Gruppens_par=("beste_par", "sum"))
    )
    df_sum.rename(columns={"Gruppens_par": "Gruppens par"}, inplace=True)


    return df_sum

def resultat_goy_pall(turneringsid):
    df = t.resultat()
    df = df[df[c.TURNERINGSID].astype(int) == turneringsid]
    df_plass = (
        df
        .groupby("Spiller")["Plass"]
        .value_counts()
        .unstack(fill_value=0)
        .rename(columns={
            1: "1.plass",
            2: "2.plass",
            3: "3.plass",
            4: "4.plass",
            5: "5.plass",
            6: "6.plass",
            7: "7.plass",
        })
        .sort_values(
            by=["1.plass", "2.plass"],
            ascending=[False, False]
        )
        .reset_index()
    )
    return df_plass
