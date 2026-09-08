import streamlit as st

from aiapi.back_df_round import _is_admin_player
from live_runde_test_data import TEST_PAR_BY_HULL, TEST_PLAYERS
from ui.components.html_visuals import register_btns, register_number_btn, register_tekst_btn, render_test_card


def page():
    current_player = st.session_state.get("innlogget_spiller")
    if not _is_admin_player(current_player):
        st.error("Bare admin kan se komponenttesten.")
        return

    st.subheader("Visuell komponenttest")
    render_test_card("Testkort", "Her kan vi prøve ut egne UI-komponenter før de brukes i Live Runde.")
    register_number_btn(
        value="1",
        label="Hole in one",
        key="one",
        bredde=104,
    )
    register_tekst_btn(
        tekst="Neste spiller",
        key="next_player",
        bredde=104,
    )

    st.markdown("#### register_btns test")
    hull = st.selectbox("Hull (for testinput)", options=list(TEST_PAR_BY_HULL), format_func=lambda h: f"Hull {h} (par {TEST_PAR_BY_HULL[h]})")
    par = TEST_PAR_BY_HULL[hull]
    clicked_value = register_btns(
        par=int(par),
        key="register_btns_test",
        spillere=TEST_PLAYERS,
    )
    if clicked_value:
        st.write(f"Sist trykket: {clicked_value}")
