"""Limity ruchu na endpointach uwierzytelniania.

Limiter jest domyślnie WYŁĄCZONY w TestConfig (inaczej pozostałe testy odbijałyby
się od 429), więc te testy budują własną aplikację z włączonymi limitami.
"""
import pytest

from app import create_app, db, limiter
from tests.conftest import TestConfig


class RateLimitConfig(TestConfig):
    RATELIMIT_ENABLED = True


@pytest.fixture
def limited_client():
    app = create_app(RateLimitConfig)
    with app.app_context():
        db.create_all()
        # Licznik limitera żyje w pamięci procesu i przetrwałby między testami,
        # przez co drugi test startowałby z wyczerpanym limitem.
        limiter.reset()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_login_blokowany_po_przekroczeniu_limitu(limited_client):
    """Automat zgadujący hasła dostaje 429 zamiast kolejnych prób."""
    odpowiedzi = [
        limited_client.post('/api/login', json={'username': 'ktos', 'password': 'zle'})
        for _ in range(12)
    ]
    kody = [r.status_code for r in odpowiedzi]

    assert 429 in kody, f"limit nie zadziałał, kody: {kody}"
    # Limit to 10/min — pierwsze 10 prób ma przejść normalnie (401), dopiero potem 429.
    assert kody[:10] == [401] * 10
    assert kody[10] == 429


def test_rejestracja_blokowana_po_przekroczeniu_limitu(limited_client):
    """Masowe zakładanie kont odbija się od limitu 5/godzinę."""
    kody = []
    for i in range(7):
        r = limited_client.post('/api/register', json={
            'username': f'bot{i}', 'email': f'bot{i}@example.com', 'password': 'DlugieHaslo123',
        })
        kody.append(r.status_code)

    assert kody[:5] == [201] * 5, f"pierwsze 5 rejestracji powinno przejść, kody: {kody}"
    assert kody[5] == 429
    assert kody[6] == 429
