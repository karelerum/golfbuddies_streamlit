import streamlit as st

from aiapi.tournament_admin import (
    TournamentAdminError,
    create_tournament_action,
    delete_tournament_action,
    update_tournament_action,
)
from aiapi.tournament_setup import (
    get_course_options,
    get_next_tournament_id,
    get_player_options,
    get_tournament_list_df,
    get_tournament_players,
    get_tournament_rounds,
)


def _render_sync_feedback(success_message: str, sync_report) -> None:
    if sync_report.ok and sync_report.warning_count == 0:
        st.success(success_message)
        return

    st.warning(f"{success_message}. {sync_report.status_message()}")
    if sync_report.issues:
        with st.expander("Vis detaljer"):
            for issue in sync_report.issues:
                st.write(f"- {issue.to_display_text()}")


def _render_action_result(action_result) -> None:
    _render_sync_feedback(action_result.message, action_result.sync_report)


def _move_item(items: list[dict], index: int, direction: int) -> None:
    new_index = index + direction
    if new_index < 0 or new_index >= len(items):
        return
    items[index], items[new_index] = items[new_index], items[index]


def page():
    st.title("Turneringsoppsett")

    if "tournament_setup_mode" not in st.session_state:
        st.session_state.tournament_setup_mode = None

    notice = st.session_state.pop("tournament_setup_notice", None)
    if notice:
        if notice["level"] == "success":
            st.success(notice["message"])
        else:
            st.warning(notice["message"])

    tournament_df = get_tournament_list_df()

    if st.session_state.tournament_setup_mode is None:
        col_new, col_edit = st.columns(2)

        with col_new:
            if st.button("Ny turnering", type="primary", width="stretch"):
                st.session_state.tournament_setup_mode = "ny"
                st.rerun()

        with col_edit:
            if st.button("Rediger turnering", width="stretch"):
                st.session_state.tournament_setup_mode = "rediger"
                st.rerun()

        st.divider()
        st.subheader("Eksisterende turneringer")
        if not tournament_df.empty:
            st.dataframe(tournament_df[["turneringsid", "turneringsnavn", "aar", "type"]], hide_index=True, width="stretch")
        else:
            st.write("Ingen turneringer opprettet ennå.")
        return

    if st.session_state.tournament_setup_mode == "ny":
        st.subheader("Opprett ny turnering")
        if st.button("Tilbake", key="back_tournament_setup_new"):
            st.session_state.tournament_setup_mode = None
            st.rerun()

        if "tournament_setup_new" not in st.session_state:
            st.session_state.tournament_setup_new = {
                "type": "Vinter",
                "year": 2026,
                "name": "",
                "players": [],
                "courses": [],
            }

        wizard = st.session_state.tournament_setup_new
        player_options = get_player_options()
        course_options = get_course_options()

        st.markdown("### Steg 1: Velg type")
        wizard["type"] = st.radio("Turnering type", ["Vinter", "Sommer"], index=0 if wizard["type"] == "Vinter" else 1, label_visibility="collapsed")

        st.markdown("### Steg 2: År")
        wizard["year"] = st.number_input("År", value=int(wizard["year"]), min_value=2020, max_value=2035, label_visibility="collapsed")
        st.info(f"Generert TurneringsId: {get_next_tournament_id(int(wizard['year']))}")

        st.markdown("### Steg 3: Turneringsnavn")
        wizard["name"] = st.text_input("Turneringsnavn", value=wizard["name"], label_visibility="collapsed", placeholder="F.eks. VO 27")

        st.markdown("### Steg 4: Velg spillere")
        wizard["players"] = st.multiselect("Spillere", options=player_options, default=wizard["players"], label_visibility="collapsed")
        st.caption(f"Valgt: {len(wizard['players'])} spillere")

        st.markdown("### Steg 5: Velg baner")
        if wizard["courses"]:
            for index, course_name in enumerate(wizard["courses"]):
                col_course, col_remove = st.columns([4, 1])
                with col_course:
                    st.write(f"{index + 1}. {course_name}")
                with col_remove:
                    if st.button("Fjern", key=f"remove_new_course_{index}"):
                        wizard["courses"].pop(index)
                        st.rerun()

        add_course = st.selectbox("Legg til bane", options=course_options, key="add_new_tournament_course")
        if st.button("Legg til bane", key="add_new_tournament_course_btn"):
            if add_course:
                wizard["courses"].append(add_course)
                st.rerun()

        st.divider()
        if st.button("Opprett turnering", type="primary", width="stretch"):
            try:
                action_result = create_tournament_action(
                    wizard["name"],
                    wizard["type"],
                    int(wizard["year"]),
                    wizard["players"],
                    wizard["courses"],
                )
            except TournamentAdminError as exc:
                st.error(str(exc))
            else:
                _render_action_result(action_result)

    elif st.session_state.tournament_setup_mode == "rediger":
        st.subheader("Rediger turnering")
        if st.button("Tilbake", key="back_tournament_setup_edit"):
            st.session_state.tournament_setup_mode = None
            st.rerun()

        if tournament_df.empty:
            st.write("Ingen turneringer å redigere.")
            return

        tournament_options = {
            str(row["turneringsid"]): f"{row['turneringsid']} - {row['turneringsnavn']}"
            for _, row in tournament_df.iterrows()
        }
        selected_tournament_id = st.selectbox(
            "Velg turnering å redigere",
            options=list(tournament_options.keys()),
            format_func=tournament_options.get,
            label_visibility="collapsed",
        )

        col_delete, col_spacer = st.columns([1, 3])
        with col_delete:
            if st.button("Slett turnering", type="secondary", width="stretch"):
                try:
                    action_result = delete_tournament_action(selected_tournament_id)
                except TournamentAdminError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("tournament_setup_edit", None)
                    st.session_state.pop("tournament_setup_edit_id", None)
                    st.session_state.tournament_setup_notice = {
                        "level": action_result.notice_level,
                        "message": f"{action_result.message}. {action_result.sync_report.status_message()}" if not action_result.ok else action_result.message,
                    }
                    st.session_state.tournament_setup_mode = None
                    st.rerun()

        if st.session_state.get("tournament_setup_edit_id") != selected_tournament_id:
            selected_row = tournament_df.loc[tournament_df["turneringsid"].astype(str) == str(selected_tournament_id)].iloc[0]
            st.session_state.tournament_setup_edit_id = selected_tournament_id
            st.session_state.tournament_setup_edit = {
                "name": str(selected_row["turneringsnavn"]),
                "type": str(selected_row.get("type") or "Vinter"),
                "players": get_tournament_players(selected_tournament_id),
                "rounds": get_tournament_rounds(selected_tournament_id),
            }

        edit_wizard = st.session_state.tournament_setup_edit
        if "players" not in edit_wizard:
            edit_wizard["players"] = get_tournament_players(selected_tournament_id)
        if "rounds" not in edit_wizard:
            legacy_courses = edit_wizard.pop("courses", []) if "courses" in edit_wizard else []
            existing_rounds = get_tournament_rounds(selected_tournament_id)
            edit_wizard["rounds"] = existing_rounds or [{"rundeid": None, "bane": str(course)} for course in legacy_courses]
        if "name" not in edit_wizard:
            selected_row = tournament_df.loc[tournament_df["turneringsid"].astype(str) == str(selected_tournament_id)].iloc[0]
            edit_wizard["name"] = str(selected_row["turneringsnavn"])
        if "type" not in edit_wizard:
            selected_row = tournament_df.loc[tournament_df["turneringsid"].astype(str) == str(selected_tournament_id)].iloc[0]
            edit_wizard["type"] = str(selected_row.get("type") or "Vinter")

        player_options = get_player_options()
        course_options = get_course_options()

        st.markdown("### Steg 1: Turneringsnavn")
        edit_wizard["name"] = st.text_input("Turneringsnavn", value=edit_wizard["name"], label_visibility="collapsed")

        st.markdown("### Steg 2: Type")
        edit_wizard["type"] = st.radio("Turnering type", ["Vinter", "Sommer"], index=0 if edit_wizard["type"] == "Vinter" else 1, label_visibility="collapsed")

        st.markdown("### Steg 3: Spillere")
        edit_wizard["players"] = st.multiselect(
            "Spillere",
            options=player_options,
            default=edit_wizard["players"],
            label_visibility="collapsed",
        )
        st.caption(f"Valgt: {len(edit_wizard['players'])} spillere")

        st.markdown("### Steg 4: Baner")
        for index, round_item in enumerate(edit_wizard["rounds"]):
            course_name = str(round_item.get("bane") or "")
            col_course, col_up, col_down, col_remove = st.columns([4, 1, 1, 1])
            with col_course:
                st.write(f"{index + 1}. {course_name}")
                if round_item.get("rundeid"):
                    st.caption(f"RundeId: {round_item['rundeid']}")
            with col_up:
                if st.button("Opp", key=f"move_edit_course_up_{index}", disabled=index == 0):
                    _move_item(edit_wizard["rounds"], index, -1)
                    st.rerun()
            with col_down:
                if st.button("Ned", key=f"move_edit_course_down_{index}", disabled=index == len(edit_wizard['rounds']) - 1):
                    _move_item(edit_wizard["rounds"], index, 1)
                    st.rerun()
            with col_remove:
                if st.button("Fjern", key=f"remove_edit_course_{index}"):
                    edit_wizard["rounds"].pop(index)
                    st.rerun()

        add_course = st.selectbox("Legg til bane", options=course_options, key="add_edit_tournament_course")
        if st.button("Legg til bane", key="add_edit_tournament_course_btn"):
            if add_course:
                edit_wizard["rounds"].append({"rundeid": None, "bane": add_course})
                st.rerun()

        st.divider()
        if st.button("Lagre endringer", type="primary", width="stretch"):
            try:
                action_result = update_tournament_action(
                    selected_tournament_id,
                    edit_wizard["name"],
                    edit_wizard["type"],
                    edit_wizard["players"],
                    edit_wizard["rounds"],
                )
            except TournamentAdminError as exc:
                st.error(str(exc))
            else:
                st.session_state.tournament_setup_edit["rounds"] = get_tournament_rounds(selected_tournament_id)
                st.session_state.tournament_setup_edit["players"] = get_tournament_players(selected_tournament_id)
                _render_action_result(action_result)