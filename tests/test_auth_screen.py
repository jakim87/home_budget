"""Ekran logowania: panel marki obok formularza.

Modal logowania jest pierwszym kontaktem z aplikacja — samotny formularz nie
mowil, co to za aplikacja i po co zakladac konto. Panel `_auth_brand_panel.html`
jest wlaczany do `base.html`, wiec zgubienie `{% include %}` przy edycji szablonu
przeszloby przez zielone testy; te asercje to lapia.
"""


def test_ekran_logowania_przedstawia_aplikacje(client):
    html = client.get('/login').get_data(as_text=True)

    assert 'Ile mam kasy' in html
    assert 'Kontroluj swoje wydatki i przychody w jednym miejscu.' in html
    # Trzy obietnice produktu z panelu marki.
    assert 'Import z wyciągów' in html
    assert 'Kategoryzacja i wykresy' in html
    assert 'Budżet miesięczny' in html


def test_panel_marki_nie_wypycha_formularzy_ani_linkow_prawnych(client):
    """Panel jest dodatkiem — pola, demo i linki do dokumentow zostaja bez zmian."""
    html = client.get('/login').get_data(as_text=True)

    assert 'id="login-form"' in html
    assert 'id="register-form"' in html
    assert 'id="auth-view-login"' in html
    assert 'id="auth-view-register"' in html
    assert '/regulamin' in html
    assert '/polityka-prywatnosci' in html


def test_gosc_na_stronie_glownej_widzi_wizytowke(client):
    html = client.get('/').get_data(as_text=True)

    assert 'id="landing"' in html
    assert 'id="login-form"' not in html
    assert 'href="/login"' in html


def test_zalogowany_na_stronie_glownej_widzi_aplikacje(logged_in_client):
    html = logged_in_client.get('/').get_data(as_text=True)

    assert 'id="login-form"' in html
    assert 'id="landing"' not in html


def test_zalogowany_na_login_wraca_do_aplikacji(logged_in_client):
    response = logged_in_client.get('/login')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')
