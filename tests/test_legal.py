"""Strony informacyjne: regulamin, polityka prywatności (RODO), informacja o autorze.

Kluczowy wymóg: dokumenty muszą być dostępne BEZ logowania — linkujemy je
z modalu rejestracji, więc użytkownik czyta je zanim założy konto.
"""

LEGAL_PATHS = ['/regulamin', '/polityka-prywatnosci', '/o-aplikacji']


def test_strony_informacyjne_dostepne_bez_logowania(client):
    for path in LEGAL_PATHS:
        response = client.get(path)
        assert response.status_code == 200, f"{path} zwrocilo {response.status_code}"


def test_regulamin_zawiera_kluczowe_postanowienia(client):
    html = client.get('/regulamin').get_data(as_text=True)

    assert 'Regulamin aplikacji' in html
    assert 'licencji MIT' in html
    # Aplikacja nie laczy sie z bankami i nie doradza finansowo — to musi byc napisane wprost.
    assert 'nie łączy się z bankami' in html
    assert 'doradztwa finansowego' in html
    # Odsylacz do polityki prywatnosci (jeden dokument nie zastepuje drugiego).
    assert '/polityka-prywatnosci' in html


def test_polityka_prywatnosci_zawiera_elementy_wymagane_przez_rodo(client):
    html = client.get('/polityka-prywatnosci').get_data(as_text=True)

    assert 'Administratorem danych' in html
    assert 'art. 6 ust. 1 lit. b RODO' in html          # podstawa prawna
    assert 'Okres przechowywania' in html                # retencja
    assert '60 dni' in html                              # archiwum usunietych transakcji
    assert 'Prezesa Urzędu Ochrony Danych Osobowych' in html   # organ nadzorczy
    assert 'art. 22 RODO' in html                        # brak decyzji automatycznych


def test_strona_o_aplikacji_wskazuje_autora(client, app):
    html = client.get('/o-aplikacji').get_data(as_text=True)

    assert 'Autor' in html
    assert app.config['APP_AUTHOR'] in html
    assert app.config['APP_AUTHOR_URL'] in html


def test_dane_kontaktowe_pochodza_z_konfiguracji(client, app):
    """Administrator instancji nadpisuje kontakt z .env — strony mają to uwzględniać."""
    app.config['APP_ADMIN_NAME'] = 'Jan Testowy'
    app.config['APP_CONTACT_EMAIL'] = 'kontakt@example.com'

    html = client.get('/polityka-prywatnosci').get_data(as_text=True)

    assert 'Jan Testowy' in html
    assert 'kontakt@example.com' in html


def test_aplikacja_linkuje_do_dokumentow(client, app):
    """Stopka SPA i modal logowania prowadzą do wszystkich trzech dokumentów."""
    html = client.get('/').get_data(as_text=True)

    for path in LEGAL_PATHS:
        assert path in html, f"brak linku do {path} w base.html"
    assert app.config['APP_AUTHOR'] in html
    assert 'Zakładając konto akceptujesz' in html
