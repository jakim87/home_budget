// Dane przykładowe z makiety Wniosków (19 pełnych miesięcy + 1 dzień bieżącego), w kształcie
// z GET /api/init. Generator z ziarnem — te same liczby przy każdym uruchomieniu.

export const DZIS = '2026-11-01';

export const KATEGORIE = [
    ['Wynagrodzenie', 'income'], ['Inne przychody', 'income'],
    ['Mieszkanie', 'expense'], ['Media', 'expense'], ['Subskrypcje', 'expense'], ['Sport', 'expense'],
    ['Jedzenie', 'expense'], ['Restauracje', 'expense'], ['Transport', 'expense'], ['Zdrowie', 'expense'],
    ['Dom', 'expense'], ['Ubrania', 'expense'], ['Elektronika', 'expense'], ['Podróże', 'expense'],
    ['Prezenty', 'expense'], ['Zwierzęta', 'expense'], ['Przelew wewnętrzny', 'transfer'],
    ['Uzgadnianie salda', 'system_reconciliation'],
].map(([name, type], k) => ({ id: k + 1, name, type, is_system_category: type === 'system_reconciliation' }));

export const KONTA = [
    { id: 1, name: 'Konto osobiste', account_type: 'ROR', currency: 'PLN', is_favorite: true },
    { id: 2, name: 'Oszczędności', account_type: 'KO', currency: 'PLN', is_favorite: true },
    { id: 3, name: 'Karta kredytowa', account_type: 'Kredyt', currency: 'PLN' },
    { id: 6, name: 'Fundusz wakacyjny', account_type: 'KO', currency: 'PLN' },
    { id: 7, name: 'IKZE', account_type: 'IKZE', currency: 'PLN' },
    { id: 9, name: 'Kredyt hipoteczny', account_type: 'Kredyt', currency: 'PLN', is_favorite: true },
];

const M_MIAN = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];

export function zbudujTransakcje() {
    const MIESIACE = [];
    for (let y = 2025, m = 4; y < 2026 || m <= 11;) { MIESIACE.push(`${y}-${String(m).padStart(2, '0')}`); if (++m > 12) { m = 1; y++; } }
    const BIEZACY = MIESIACE.indexOf(DZIS.slice(0, 7));
    let ziarno = 11;
    const los = () => { ziarno = ziarno + 0x6D2B79F5 | 0; let t = Math.imul(ziarno ^ ziarno >>> 15, 1 | ziarno); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    const miedzy = (a, b) => a + los() * (b - a);
    const TX = [], kontrahenci = new Map();
    const idKontrahenta = n => { if (!kontrahenci.has(n)) kontrahenci.set(n, kontrahenci.size + 1); return kontrahenci.get(n); };
    const dodaj = (date, kwota, desc, kontrahent, category, account_id = 1) => TX.push({
        id: TX.length + 1, date, amount: Math.round(kwota * 100) / 100, desc, category, account_id,
        contractor_id: idKontrahenta(kontrahent), contractor_name: kontrahent,
    });
    MIESIACE.slice(0, BIEZACY).forEach(klucz => {
        const [y, m] = klucz.split('-').map(Number);
        const dni = new Date(y, m, 0).getDate();
        const d = dzien => `${klucz}-${String(Math.min(Math.max(1, Math.round(dzien)), dni)).padStart(2, '0')}`;
        const losDzien = () => d(1 + los() * (dni - 1));
        dodaj(d(10), klucz >= '2026-07' ? 9100 : 8400, `Wynagrodzenie ${M_MIAN[m - 1]} ${y}`, 'Pracodawca sp. z o.o.', 'Wynagrodzenie');
        dodaj(d(5), -(klucz >= '2026-01' ? 820 : 780), 'Opłata za mieszkanie', 'SM Zacisze', 'Mieszkanie');
        dodaj(d(20), -65, 'Internet światłowodowy', 'Orange', 'Media');
        if (m % 2 === 0) dodaj(d(15), -miedzy(170, 240), 'Prąd, rozliczenie dwumiesięczne', 'PGE', 'Media');
        dodaj(d(3), -23.99, 'Spotify Premium', 'Spotify', 'Subskrypcje', 3);
        dodaj(d(12), -(klucz >= '2026-10' ? 60 : 49), 'Netflix', 'Netflix', 'Subskrypcje', 3);
        if (klucz >= '2026-08') dodaj(d(18), -37.99, 'Disney+', 'Disney+', 'Subskrypcje', 3);
        if (klucz <= '2026-08') dodaj(d(5), -129, 'Karnet miesięczny', 'CityFit', 'Sport');
        dodaj(d(11), -1000, 'Przelew na oszczędności', 'Moje konto: Oszczędności', 'Przelew wewnętrzny', 1);
        dodaj(d(11), 1000, 'Przelew na oszczędności', 'Moje konto: Konto osobiste', 'Przelew wewnętrzny', 2);
        const zakupy = 11 + Math.floor(los() * 4);
        for (let k = 0; k < zakupy; k++) {
            const sklep = ['Biedronka', 'Lidl', 'Żabka', 'Auchan', 'Biedronka', 'Lidl'][Math.floor(los() * 6)];
            dodaj(losDzien(), -(sklep === 'Żabka' ? miedzy(15, 45) : miedzy(70, 190)), 'Zakupy spożywcze', sklep, 'Jedzenie');
        }
        const wyjscia = { '2026-07': 4, '2026-08': 7, '2026-09': 9, '2026-10': 11 }[klucz] ?? 4 + Math.floor(los() * 3);
        for (let k = 0; k < wyjscia; k++) {
            const lokal = ['Pyszne.pl', 'Bolt Food', 'Bistro Mięta', 'Pizzeria Da Grasso'][Math.floor(los() * 4)];
            dodaj(losDzien(), -miedzy(70, 140), lokal.includes('.') || lokal.startsWith('Bolt') ? 'Zamówienie z dostawą' : 'Rachunek', lokal, 'Restauracje', los() < 0.4 ? 3 : 1);
        }
        const tankowania = klucz === '2026-10' ? 2 : (m === 7 || m === 8) ? 5 : 3;
        for (let k = 0; k < tankowania; k++) dodaj(losDzien(), -(klucz === '2026-10' ? miedzy(190, 240) : miedzy(220, 290)), 'Paliwo', los() < 0.6 ? 'Orlen' : 'Shell', 'Transport');
        if (los() < 0.5) dodaj(losDzien(), -miedzy(25, 90), 'Leki', 'Apteka Gemini', 'Zdrowie');
        if (m % 4 === 0) dodaj(d(8), -180, 'Wizyta u specjalisty', 'LuxMed', 'Zdrowie');
        for (let k = 0; k < 2; k++) dodaj(losDzien(), -miedzy(30, 90), 'Chemia i kosmetyki', 'Rossmann', 'Dom');
        if (los() < 0.25) dodaj(losDzien(), -miedzy(150, 600), 'Wyposażenie mieszkania', 'IKEA', 'Dom');
        if (los() < 0.45) dodaj(losDzien(), -miedzy(120, 380), 'Zamówienie', 'Zalando', 'Ubrania', 3);
        if (m === 12) { dodaj(d(14), -260, 'Prezenty', 'Empik', 'Prezenty'); dodaj(d(16), -540, 'Prezenty', 'Allegro', 'Prezenty', 3); }
    });
    dodaj('2025-07-08', -2400, 'Rezerwacja, Chorwacja', 'Booking.com', 'Podróże', 3);
    dodaj('2025-12-04', -199, 'Słuchawki', 'Media Expert', 'Elektronika');
    dodaj('2026-02-14', -180, 'Bilety', 'PKP Intercity', 'Podróże');
    dodaj('2026-05-20', 1240, 'Zwrot podatku PIT-37', 'Urząd Skarbowy', 'Inne przychody');
    dodaj('2026-07-03', -2800, 'Rezerwacja, Sycylia', 'Booking.com', 'Podróże', 3);
    dodaj('2026-10-14', -3499, 'Laptop Lenovo IdeaPad', 'Media Expert', 'Elektronika');
    dodaj('2026-10-22', -320, 'Szczepienie i badania', 'Gabinet weterynaryjny Azor', 'Zwierzęta');
    dodaj('2026-10-25', 1150, 'Sprzedaż roweru', 'OLX', 'Inne przychody');
    dodaj('2026-11-01', -23.4, 'Zakupy spożywcze', 'Żabka', 'Jedzenie');
    MIESIACE.slice(0, BIEZACY).forEach((klucz, j) => {
        const dlug = -TX.filter(t => t.account_id === 3 && t.date.startsWith(klucz) && t.category !== 'Przelew wewnętrzny').reduce((s, t) => s + t.amount, 0);
        if (dlug > 0 && j + 1 < BIEZACY) {
            dodaj(`${MIESIACE[j + 1]}-25`, -dlug, 'Spłata karty kredytowej', 'Moje konto: Karta kredytowa', 'Przelew wewnętrzny', 1);
            dodaj(`${MIESIACE[j + 1]}-25`, dlug, 'Spłata karty kredytowej', 'Moje konto: Konto osobiste', 'Przelew wewnętrzny', 3);
        }
    });
    MIESIACE.slice(0, BIEZACY).forEach(klucz => {
        const nazwa = id => KONTA.find(k => k.id === id).name;
        const przelew = (dzien, kwota, tytul, z, na) => {
            dodaj(`${klucz}-${dzien}`, -kwota, tytul, `Moje konto: ${nazwa(na)}`, 'Przelew wewnętrzny', z);
            dodaj(`${klucz}-${dzien}`, kwota, tytul, `Moje konto: ${nazwa(z)}`, 'Przelew wewnętrzny', na);
        };
        przelew('02', 2100, 'Rata kredytu hipotecznego', 1, 9);
        przelew('15', 300, 'Wpłata na IKZE', 1, 7);
        if (klucz.endsWith('-06')) przelew('28', 2500, 'Na wyjazd', 6, 1); else przelew('15', 400, 'Fundusz wakacyjny', 1, 6);
    });
    return { transakcje: TX, kontrahenci };
}
