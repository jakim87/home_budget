// --- KOMUNIKAT O ZMIANIE DOKUMENTÓW PRAWNYCH ---
// Serwer w /api/init (`legal_notice`) mówi, czy baner ma się pokazać (data zmiany
// dokumentów jest nowsza niż ta, którą użytkownik potwierdził) i podaje streszczenie
// zmian od jego ostatniej wizyty (`changes`: [{date, od, punkty}]). Front tylko wyświetla.

function czyPokazacKomunikatPrawny(notice) {
    return !!(notice && notice.show);
}

// „1 zmiana", „2 zmiany", „5 zmian", „12 zmian", „22 zmiany"
function liczbaZmianTekst(n) {
    const reszta10 = n % 10, reszta100 = n % 100;
    let forma = 'zmian';
    if (n === 1) forma = 'zmiana';
    else if (reszta10 >= 2 && reszta10 <= 4 && !(reszta100 >= 12 && reszta100 <= 14)) forma = 'zmiany';
    return `${n} ${forma}`;
}

function renderKomunikatPrawny(notice) {
    const el = document.getElementById('legal-notice');
    if (!el) return;
    const zmiany = (notice && notice.changes) || [];
    const licznik = document.getElementById('legal-notice-count');
    if (licznik) {
        const n = zmiany.reduce((suma, z) => suma + z.punkty.length, 0);
        licznik.textContent = `${liczbaZmianTekst(n)} od Twojej ostatniej wizyty`;
    }
    const lista = document.getElementById('legal-notice-changes');
    if (lista) {
        lista.replaceChildren();
        for (const z of zmiany) {
            const naglowek = document.createElement('h4');
            naglowek.textContent = z.od ? `${z.date} (obowiązuje od ${z.od})` : z.date;
            const ul = document.createElement('ul');
            for (const punkt of z.punkty) {
                const li = document.createElement('li');
                li.textContent = punkt;
                ul.appendChild(li);
            }
            lista.append(naglowek, ul);
        }
    }
    el.classList.toggle('hidden', !czyPokazacKomunikatPrawny(notice));
}

async function potwierdzKomunikatPrawny() {
    try {
        const response = await fetch('/api/legal-ack', { method: 'POST' });
        if (!response.ok) {
            showToast('Nie udało się zapisać potwierdzenia.', 'error');
            return;
        }
        renderKomunikatPrawny({ show: false });
    } catch (error) {
        console.error('Błąd zapisu potwierdzenia dokumentów:', error);
        showToast('Nie udało się zapisać potwierdzenia.', 'error');
    }
}
