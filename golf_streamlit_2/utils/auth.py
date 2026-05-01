import streamlit as st


AUTH_KEY = "authenticated_user"


def get_authenticated_user() -> str | None:
    return st.session_state.get(AUTH_KEY)


def is_authenticated() -> bool:
    return bool(get_authenticated_user())


def _get_passwords() -> dict[str, str]:
    auth = st.secrets.get("auth", {})
    passwords = auth.get("passwords", {})
    return {str(k): str(v) for k, v in dict(passwords).items()}


def login_form() -> None:
    st.subheader("Logg inn")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Brukernavn")
        password = st.text_input("Passord", type="password")
        submitted = st.form_submit_button("Logg inn")

    if not submitted:
        return

    passwords = _get_passwords()
    if not username or not password:
        st.error("Fyll inn brukernavn og passord.")
        return

    if passwords.get(username) == password:
        st.session_state[AUTH_KEY] = username
        st.success(f"Innlogget som {username}")
        st.rerun()
        return

    st.error("Ugyldig brukernavn eller passord.")


def logout_button() -> None:
    user = get_authenticated_user()
    if not user:
        return

    st.sidebar.caption(f"Innlogget: {user}")
    if st.sidebar.button("Logg ut"):
        st.session_state.pop(AUTH_KEY, None)
        st.rerun()


def require_login() -> bool:
    if is_authenticated():
        return True

    st.warning("Du må logge inn for å bruke denne siden.")
    login_form()
    return False
