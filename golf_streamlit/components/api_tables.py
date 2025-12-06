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
            "background-color: #CCFFCC; font-weight: bold" if v else ""
            for v in is_value
        ]
    
    # Returnér en styler
    pivot = (
        pivot.style
        .apply(highlight, axis=1)
        .format(f.fmt) 
    )
    return pivot