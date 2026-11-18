"""Strony informacyjne: regulamin, polityka prywatności (RODO), informacja o autorze.

Kluczowy wymóg: dokumenty muszą być dostępne BEZ logowania — linkujemy je
z modalu rejestracji, więc użytkownik czyta je zanim założy konto.
"""

LEGAL_PATHS = ['/regulamin', '/polityka-prywatnosci', '/o-aplikacji', '/kalkulator-kredytu']


def test_strony_informacyjne_dostepne_bez_logowania(client):
    for path in LEGAL_PATHS:
        response = client.get(path)
        assert response.status_code == 200, f"{path} zwrocilo {response.status_code}"


def test_regulamin_zawiera_kluczowe_postanowienia(client):
    html = client.get('/regulamin').get_data(as_text=True)

    assert 'Regulamin aplikacji' in html
    assert 'Business Source License 1.1' in html
    assert 'licencji MIT' not in html    # obowiązuje BSL; MIT dopiero od Change Date
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
    assert 'kasowane od razu i trwale' in html           # usuniete transakcje bez archiwum (#161)
    assert '60 dni' not in html
    assert 'Prezesa Urzędu Ochrony Danych Osobowych' in html   # organ nadzorczy
    assert 'art. 22 RODO' in html                        # brak decyzji automatycznych
    # Retencja wszystkiego, co trzyma serwer — także poza bazą aplikacji.
    assert 'Logi serwera WWW' in html                    # IP każdej wizyty, 14 dni
    assert 'Kopie zapasowe bazy danych' in html          # usunięte dane żyją w kopiach do 14 dni


def test_polityka_wskazuje_dostawce_poczty_dla_gmaila(client, app):
    app.config['APP_CONTACT_EMAIL'] = 'ktos@gmail.com'
    assert 'Google Ireland Limited' in client.get('/polityka-prywatnosci').get_data(as_text=True)

    app.config['APP_CONTACT_EMAIL'] = 'kontakt@example.com'
    assert 'Google Ireland Limited' not in client.get('/polityka-prywatnosci').get_data(as_text=True)


def test_skrypt_przesuwa_change_date_o_4_lata():
    """Workflow wydań przesuwa datę BSL przy MINOR — logika siedzi w .github/scripts."""
    import importlib.util
    from datetime import date
    from pathlib import Path

    sciezka = Path(__file__).resolve().parent.parent / '.github' / 'scripts' / 'przesun_change_date.py'
    spec = importlib.util.spec_from_file_location('przesun_change_date', sciezka)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    wynik = modul.przesun('Licensor: x\nChange Date:          2028-01-01\nChange License: MIT\n', date(2026, 12, 3))
    assert 'Change Date:          2030-12-03\n' in wynik
    assert 'Change License: MIT' in wynik          # reszta pliku nietknięta

    licencja = Path(__file__).resolve().parent.parent / 'LICENSE'
    assert modul.WZORZEC.search(licencja.read_text(encoding='utf-8'))   # wzorzec pasuje do prawdziwego pliku


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
    html = client.get('/login').get_data(as_text=True)

    for path in LEGAL_PATHS:
        assert path in html, f"brak linku do {path} w base.html"
    assert app.config['APP_AUTHOR'] in html
    assert 'Zakładając konto akceptujesz' in html
