// =============================================
// ZAKŁADKA: BUDŻET (plan miesięczny vs wykonanie)
// =============================================
//
// W odróżnieniu od Dashboardu i Raportów ta zakładka NIE liczy nic w przeglądarce —
// wszystkie kwoty przychodzą policzone z GET /api/budgets/<rok>/<miesiac>. Powód:
// budżet jest świadomy podziałów transakcji i rezerwacji z harmonogramu, a globalny
// stan frontu nie zawiera ani jednego, ani drugiego.

let budgetDate = new Date();
let budgetDane = null;

const BUDGET_MIESIACE = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
    'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'];

function budgetFmt(v) {
    return `${Math.abs(v).toFixed(2).replace('.', ',')} PLN`;
}

/**
 * Stan wiersza budżetu: szerokości segmentów paska i kolor.
 *
 * Kierunek zależy od typu kategorii: przekroczenie planu wydatków to zła wiadomość
 * (czerwony), osiągnięcie planu przychodów — dobra (zielony). Ten sam procent znaczy
 * coś przeciwnego po obu stronach.
 *
 * Segment rezerwacji dokłada się DO wykonania (nie obok), bo razem pokazują, ile
 * z planu jest już zajęte. Oba przycinamy do 100%, żeby pasek nie wyjechał z komórki.
 */
function budgetStanPozycji(p) {
    const plan = Number(p.plan) || 0;
    const wykonane = Number(p.wykonane) || 0;
    const zarezerwowane = Number(p.zarezerwowane) || 0;
    if (plan <= 0) {
        return { procent: null, szerWykonane: 0, szerRezerwacji: 0, kolor: 'bg-slate-300', ostrzezenie: false };
    }

    const procent = ((wykonane + zarezerwowane) / plan) * 100;
    const szerWykonane = Math.min((wykonane / plan) * 100, 100);
    const szerRezerwacji = Math.min((zarezerwowane / plan) * 100, 100 - szerWykonane);

    let kolor;
    if (p.category_type === 'income') {
        kolor = procent >= 100 ? 'bg-emerald-500' : 'bg-blue-500';
    } else {
        kolor = procent > 100 ? 'bg-rose-500' : (procent >= 85 ? 'bg-amber-500' : 'bg-emerald-500');
    }
    // Ostrzegamy tylko po stronie wydatków — przekroczony plan przychodów to sukces.
    return {
        procent, szerWykonane, szerRezerwacji, kolor,
        ostrzezenie: p.category_type === 'expense' && procent > 100,
    };
}

/** Ile procent miesiąca minęło — odniesienie dla paska ("tu powinieneś być"). */
function budgetUplywMiesiaca(rok, miesiac, dzis = new Date()) {
    const dniWMiesiacu = new Date(rok, miesiac, 0).getDate();
    if (dzis.getFullYear() !== rok || dzis.getMonth() + 1 !== miesiac) {
        // Miesiąc miniony albo przyszły — kreska "dziś" nie ma sensu.
        return null;
    }
    return (dzis.getDate() / dniWMiesiacu) * 100;
}

async function renderBudget() {
    const rok = budgetDate.getFullYear();
    const miesiac = budgetDate.getMonth() + 1;
    document.getElementById('budget-month-display').innerText = `${BUDGET_MIESIACE[miesiac - 1]} ${rok}`;

    try {
        const resp = await fetch(`/api/budgets/${rok}/${miesiac}`);
        if (!resp.ok) throw new Error('blad');
        budgetDane = await resp.json();
    } catch (e) {
        showToast('Nie udało się pobrać budżetu', 'error');
        return;
    }
    budgetRenderujPodsumowanie();
    budgetRenderujWiersze();
}

function budgetChangeMonth(offset) {
    budgetDate.setMonth(budgetDate.getMonth() + offset);
    renderBudget();
}

function budgetRenderujPodsumowanie() {
    const d = budgetDane;
    document.getElementById('budget-planned-income').innerText = budgetFmt(d.planowane_przychody);
    document.getElementById('budget-planned-expense').innerText = budgetFmt(d.planowane_wydatki);

    const bilans = document.getElementById('budget-balance');
    bilans.innerText = `${d.bilans_planu < 0 ? '−' : ''}${budgetFmt(d.bilans_planu)}`;
    bilans.className = `text-2xl font-bold ${d.bilans_planu < 0 ? 'text-rose-600' : 'text-slate-800'}`;

    // Plan wydatków ponad plan przychodów jest dozwolony — to decyzja użytkownika,
    // nie błąd. Aplikacja ma o tym powiedzieć wprost, nie zablokować zapisu.
    const baner = document.getElementById('budget-warning');
    baner.classList.toggle('hidden', d.bilans_planu >= 0);
    if (d.bilans_planu < 0) {
        baner.innerText = `Plan wydatków przekracza plan przychodów o ${budgetFmt(d.bilans_planu)}.`;
    }
}

function budgetRenderujWiersze() {
    const uplyw = budgetUplywMiesiaca(budgetDane.year, budgetDane.month);
    const grupy = { income: 'Przychody', expense: 'Wydatki' };
    let html = '';

    for (const [typ, etykieta] of Object.entries(grupy)) {
        const pozycje = budgetDane.pozycje.filter(p => p.category_type === typ);
        if (!pozycje.length) continue;
        html += `<tr class="bg-slate-50"><td colspan="5" class="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">${etykieta}</td></tr>`;
        html += pozycje.map(p => budgetWierszHtml(p, uplyw)).join('');
    }

    document.getElementById('budget-rows').innerHTML = html ||
        '<tr><td colspan="5" class="p-6 text-center text-slate-400 text-sm">Brak kategorii przychodów i wydatków.</td></tr>';
}

function budgetWierszHtml(p, uplyw) {
    const stan = budgetStanPozycji(p);
    const planValue = p.plan === null ? '' : Number(p.plan).toFixed(2);
    const kreska = uplyw === null ? '' :
        `<div class="absolute top-0 bottom-0 w-px bg-slate-500/60" style="left:${uplyw.toFixed(1)}%" title="Upłynęło ${uplyw.toFixed(0)}% miesiąca"></div>`;

    return `
        <tr class="hover:bg-slate-50/70">
            <td class="px-4 py-3 text-sm text-slate-700">
                ${escapeHtml(p.category_name)}
                ${stan.ostrzezenie ? '<span class="ml-2 text-xs font-semibold text-rose-600">przekroczono</span>' : ''}
            </td>
            <td class="px-4 py-3 text-right">
                <input type="number" step="0.01" min="0" value="${planValue}" placeholder="—"
                       onchange="budgetZapiszPlan(${p.category_id}, this.value)"
                       class="w-28 p-1.5 text-right border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                ${budgetSugestiaHtml(p)}
            </td>
            <td class="px-4 py-3 text-right text-sm text-slate-700">${budgetFmt(p.wykonane)}</td>
            <td class="px-4 py-3 text-right text-sm ${p.zarezerwowane > 0 ? 'text-slate-500' : 'text-slate-300'}">${budgetFmt(p.zarezerwowane)}</td>
            <td class="px-4 py-3 w-1/3">
                <div class="relative h-3 bg-slate-100 rounded-full overflow-hidden">
                    <div class="absolute inset-y-0 left-0 ${stan.kolor}" style="width:${stan.szerWykonane.toFixed(1)}%"></div>
                    <div class="absolute inset-y-0 ${stan.kolor} opacity-40"
                         style="left:${stan.szerWykonane.toFixed(1)}%;width:${stan.szerRezerwacji.toFixed(1)}%;background-image:repeating-linear-gradient(45deg,transparent,transparent 3px,rgba(255,255,255,.6) 3px,rgba(255,255,255,.6) 6px)"></div>
                    ${kreska}
                </div>
                <p class="mt-1 text-xs text-slate-400">${stan.procent === null ? 'bez planu' : `${stan.procent.toFixed(0)}% planu`}</p>
            </td>
        </tr>`;
}

function budgetSugestiaHtml(p) {
    const s = p.sugestia || {};
    if (s.kwota === null || s.kwota === undefined) {
        return `<p class="mt-1 text-xs text-slate-400">${escapeHtml(s.podstawa || '')}</p>`;
    }
    // Podpowiedź mówi, ile BYŁO, nie ile powinno być — aplikacja nie jest doradcą
    // finansowym i nie udaje, że wie lepiej.
    const zakres = `zakres ${budgetFmt(s.zakres_min)} – ${budgetFmt(s.zakres_max)}`;
    const rokTemu = s.rok_temu === null || s.rok_temu === undefined ? '' :
        `<br><span class="text-slate-400">rok temu w tym miesiącu: ${budgetFmt(s.rok_temu)}</span>`;
    return `
        <p class="mt-1 text-xs text-right">
            <button type="button" onclick="budgetZapiszPlan(${p.category_id}, ${s.kwota})"
                    class="text-blue-600 hover:underline" title="${escapeHtml(s.podstawa)}; ${zakres}">
                ${escapeHtml(s.podstawa)}: ${budgetFmt(s.kwota)}
            </button>${rokTemu}
        </p>`;
}

async function budgetZapiszPlan(categoryId, wartosc) {
    const rok = budgetDane.year;
    const miesiac = budgetDane.month;
    const pusta = wartosc === '' || wartosc === null;

    const resp = await fetch(`/api/budgets/${rok}/${miesiac}/${categoryId}`, {
        method: pusta ? 'DELETE' : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: pusta ? null : JSON.stringify({ amount: String(wartosc) }),
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        showToast(typeof err.error === 'string' ? err.error : 'Nie udało się zapisać planu', 'error');
    }
    renderBudget();
}
