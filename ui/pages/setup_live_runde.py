import streamlit as st
import pandas as pd

from aiapi.back_df_round import _is_admin_player
from aiapi.live_round import LiveRoundError, create_live_round, get_live_round_candidates, get_live_round_details, is_test_session, update_live_round_setup
from aiapi.round_result import get_tournament_p6_totals
from aiapi.tournament_setup import get_course_options, get_player_options, get_tournament_list_df
from config.constants import LIVE_ROUND_TYPE_6P, LIVE_ROUND_TYPE_SLAG, LIVE_ROUND_TYPES, TEST_LIVE_HOLES


def _selected_players(group_number: int, player_options: list[str]) -> list[str]:
    selected_players = []
    other_group = 2 if group_number == 1 else 1
    player_row = st.container(horizontal=True)
    for player_name in player_options:
        other_group_selected = st.session_state.get(f"live_group_{other_group}_{player_name}", False)
        if player_row.checkbox(
            player_name,
            key=f"live_group_{group_number}_{player_name}",
            disabled=other_group_selected,
        ):
            selected_players.append(player_name)
    return selected_players


def page():
    current_player = st.session_state.get("innlogget_spiller")
    if not _is_admin_player(current_player):
        st.error("Bare admin kan sette opp en live-runde.")
        return

    edit_rundeid = st.session_state.get("live_edit_rundeid")
    editing_session = None
    if edit_rundeid:
        try:
            editing_session = get_live_round_details(str(edit_rundeid))
        except LiveRoundError as exc:
            st.error(str(exc))
            st.session_state.pop("live_edit_rundeid", None)

    seed_key = f"live_edit_seeded_{edit_rundeid}"
    if editing_session and not st.session_state.get(seed_key):
        for player in editing_session["spillere"]:
            st.session_state[f"live_group_{player['gruppe']}_{player['spiller']}"] = True
            st.session_state[f"live_startverdi_{player['spiller']}"] = player.get("startverdi", 0)
        st.session_state[seed_key] = True

    with st.container(horizontal=True, vertical_alignment="center"):
        st.subheader("Rediger live-runde" if editing_session else "Setup runde")
        if st.button("Tilbake"):
            st.session_state.pop("live_edit_rundeid", None)
            st.session_state.pop(seed_key, None)
            st.session_state.live_runde_view = "oversikt"
            st.rerun()

    title = st.text_input("Tittel", value=editing_session["tittel"] if editing_session else "", key="live_round_title")

    type_runde_default = editing_session.get("type_runde", LIVE_ROUND_TYPE_SLAG) if editing_session else LIVE_ROUND_TYPE_SLAG
    type_runde = st.selectbox(
        "Type runde",
        options=LIVE_ROUND_TYPES,
        index=LIVE_ROUND_TYPES.index(type_runde_default) if type_runde_default in LIVE_ROUND_TYPES else 0,
        disabled=bool(editing_session),
    )

    test_ind = st.checkbox(
        "Test",
        value=is_test_session(editing_session) if editing_session else False,
        disabled=bool(editing_session),
        key="live_round_test_ind",
    )
    if test_ind:
        st.caption(
            f"Testrunde: kun {TEST_LIVE_HOLES} hull, og ingenting lagres til Google Sheets, "
            "vanlig runde-tabell, resultat eller merker. Kilderunden låses ikke."
        )

    source_rundeid = None
    new_round_turneringsid = None
    new_round_bane = None
    if editing_session:
        st.caption(f"Kilderunde: {editing_session['source_rundeid']} (kan ikke endres)")
    elif type_runde == LIVE_ROUND_TYPE_6P:
        round_source_mode = (
            "Velg eksisterende runde"
            if test_ind
            else st.radio("Kilde", ["Velg eksisterende runde", "Opprett ny runde"], key="live_6p_round_source", horizontal=True)
        )
        if round_source_mode == "Velg eksisterende runde":
            candidates_df = get_live_round_candidates(include_active=test_ind)
            if candidates_df.empty:
                st.info("Det finnes ingen ikke-fullførte runder tilgjengelig for Live Runde.")
            else:
                round_labels = {
                    str(row["rundeid"]): f"{row['turneringsid']} - Runde {row['runde']} - {row['bane']}"
                    for _, row in candidates_df.iterrows()
                }
                source_rundeid = st.selectbox(
                    "Velg runde",
                    options=list(round_labels),
                    format_func=round_labels.get,
                )
        else:
            tournament_df = get_tournament_list_df()
            if tournament_df.empty:
                st.info("Fant ingen turneringer.")
            else:
                tournament_labels = {
                    str(row["turneringsid"]): f"{row['turneringsid']} - {row['turneringsnavn']}"
                    for _, row in tournament_df.iterrows()
                }
                new_round_turneringsid = st.selectbox("Velg turnering", options=list(tournament_labels), format_func=tournament_labels.get)
                course_options = get_course_options()
                if course_options:
                    new_round_bane = st.selectbox("Velg bane", options=course_options)
                else:
                    st.info("Fant ingen baner.")
    else:
        candidates_df = get_live_round_candidates(include_active=test_ind)
        if candidates_df.empty:
            st.info("Det finnes ingen ikke-fullførte runder tilgjengelig for Live Runde.")
        else:
            round_labels = {
                str(row["rundeid"]): f"{row['turneringsid']} - Runde {row['runde']} - {row['bane']}"
                for _, row in candidates_df.iterrows()
            }
            source_rundeid = st.selectbox(
                "Velg runde",
                options=list(round_labels),
                format_func=round_labels.get,
            )

    player_options = sorted(set(get_player_options()))
    if not player_options:
        st.info("Fant ingen spillere å velge mellom.")
        return

    st.markdown("#### Gruppe 1")
    group_1 = _selected_players(1, player_options)
    if len(group_1) > 4:
        st.error("Gruppe 1 kan ha maksimalt fire spillere.")

    st.markdown("#### Gruppe 2 (valgfri)")
    group_2 = _selected_players(2, player_options)
    if len(group_2) > 4:
        st.error("Gruppe 2 kan ha maksimalt fire spillere.")

    antall_runder_default = int(editing_session.get("antall_runder", 1)) if editing_session else 1
    antall_runder = st.selectbox("Antall runder", options=[1, 2, 3], index=[1, 2, 3].index(antall_runder_default))
    selected_players = group_1 + group_2
    startverdier = {}
    if type_runde == LIVE_ROUND_TYPE_6P and selected_players:
        st.markdown("#### Poeng fra turnering (startverdi)")
        preview_turneringsid = None
        if source_rundeid:
            candidates_df = get_live_round_candidates(include_active=test_ind)
            match = candidates_df.loc[candidates_df["rundeid"] == source_rundeid]
            if not match.empty:
                preview_turneringsid = str(match.iloc[0]["turneringsid"])
        elif new_round_turneringsid:
            preview_turneringsid = str(new_round_turneringsid)
        tournament_totals = get_tournament_p6_totals(preview_turneringsid) if preview_turneringsid else {}
        preview_df = pd.DataFrame(
            {
                "Spiller": selected_players,
                "Poeng fra turnering": [tournament_totals.get(player_name, 0) for player_name in selected_players],
            }
        )
        st.dataframe(preview_df, hide_index=True, width="stretch")
    elif type_runde == LIVE_ROUND_TYPE_SLAG and selected_players:
        st.markdown("#### Startverdier")
        st.markdown(
            """
            <style>
            .st-key-live-startverdier [data-testid="stHorizontalBlock"] {
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }
            .st-key-live-startverdier [data-testid="stColumn"] {
                min-width: 0 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="live-startverdier"):
            for player_name in selected_players:
                player_column, value_column = st.columns([3, 2], vertical_alignment="center")
                with player_column:
                    st.markdown(f"**{player_name}**")
                with value_column:
                    startverdier[player_name] = st.number_input(
                        "Startverdi",
                        min_value=-99,
                        max_value=99,
                        value=int(st.session_state.get(f"live_startverdi_{player_name}", 0)),
                        step=1,
                        key=f"live_startverdi_{player_name}",
                        label_visibility="collapsed",
                    )

    button_label = "Lagre endringer" if editing_session else "Opprett live-runde"
    can_create = editing_session is not None or source_rundeid is not None or (new_round_turneringsid and new_round_bane)
    if st.button(button_label, type="primary", disabled=not can_create):
        try:
            if editing_session:
                update_live_round_setup(str(edit_rundeid), title, group_1, group_2, startverdier, antall_runder)
                live_rundeid = str(edit_rundeid)
            else:
                live_rundeid = create_live_round(
                    source_rundeid,
                    title,
                    group_1,
                    group_2,
                    startverdier,
                    type_runde,
                    antall_runder,
                    new_round_turneringsid=new_round_turneringsid,
                    new_round_bane=new_round_bane,
                    test_ind=test_ind,
                )
        except LiveRoundError as exc:
            st.error(str(exc))
            return

        st.session_state.pop("live_edit_rundeid", None)
        st.session_state.pop(seed_key, None)
        st.session_state.live_session_id = live_rundeid
        st.session_state.live_runde_view = "slag"
        st.session_state.live_open_next_hole_for = live_rundeid
        st.rerun()