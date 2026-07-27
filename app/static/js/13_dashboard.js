// --- DASHBOARD ---
let dashboardView = 'monthly';
let dashboardChart = null;

window.setDashboardView = function(view) {
    dashboardView = view;
    const monthlyBtn = document.getElementById('dashboard-toggle-monthly');
    const yearlyBtn = document.getElementById('dashboard-toggle-yearly');
    const activeClass = 'px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white font-medium transition-colors';
    const inactiveClass = 'px-3 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200 transition-colors';
    if (view === 'monthly') {
        monthlyBtn.className = activeClass;
        yearlyBtn.className = inactiveClass;
    } else {
        yearlyBtn.className = activeClass;
        monthlyBtn.className = inactiveClass;
    }
    renderDashboardChart();
};

function renderDashboard() {
    // Net Worth
    const netWorth = accounts.reduce((sum, a) => sum + a.balance, 0);
    const netWorthEl = document.getElementById('dashboard-net-worth');
    if (netWorthEl) {
        netWorthEl.textContent = `${netWorth.toFixed(2)} PLN`;
    }

    // Karty kont
    const accountsEl = document.getElementById('dashboard-accounts');
    if (accountsEl) {
        if (accounts.length === 0) {
            accountsEl.innerHTML = '<p class="col-span-4 text-sm text-slate-500">Brak kont. Dodaj konto w zakładce Słowniki.</p>';
        } else {
            accountsEl.innerHTML = accounts.map(a => `
                <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                    <p class="text-xs font-medium text-slate-500 truncate">${a.name}${a.bank_name ? ` · ${a.bank_name}` : ''}</p>
                    ${(a.owner || a.co_owner) ? `<p class="text-xs text-slate-400 truncate">${[a.owner, a.co_owner].filter(Boolean).join(' / ')}</p>` : ''}
                    <p class="text-lg font-bold ${a.balance >= 0 ? 'text-slate-800' : 'text-rose-600'} mt-1">${a.balance.toFixed(2)} PLN</p>
                </div>
            `).join('');
        }
    }

    computeNetWorthSeries();
    renderNetWorthHistoryChart();
    renderDashboardChart();

    // Ostatnie 5 transakcji
    const recentEl = document.getElementById('dashboard-recent-tx');
    if (recentEl) {
        const recent = transactions.slice(0, 5);
        if (recent.length === 0) {
            recentEl.innerHTML = '<p class="p-4 text-sm text-slate-500">Brak transakcji.</p>';
        } else {
            recentEl.innerHTML = recent.map(t => `
                <div class="px-4 py-3 flex justify-between items-center hover:bg-slate-50">
                    <div class="min-w-0 mr-4">
                        <p class="text-sm font-medium text-slate-800 truncate">${t.desc}</p>
                        <p class="text-xs text-slate-400">${t.date} · ${t.category}${t.contractor_name ? ` · ${t.contractor_name}` : ''}</p>
                    </div>
                    <span class="text-sm font-bold whitespace-nowrap ${t.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${t.amount >= 0 ? '+' : ''}${t.amount.toFixed(2)} PLN</span>
                </div>
            `).join('');
        }
    }
}

// --- MAJĄTEK W CZASIE ---
// Net worth to suma prefiksowa transakcji w czasie (stan, nie strumień).
// Liczymy ją RAZ (jeden przebieg po już załadowanych `transactions`) —
// wybór dowolnego zakresu w UI to potem tylko wycinanie gotowej tablicy,
// bez ponownego przeliczania i bez nowego zapytania do backendu.
let netWorthSeriesFull = [];
let netWorthChart = null;

function computeNetWorthSeries() {
    if (transactions.length === 0) { netWorthSeriesFull = []; return; }

    const sorted = [...transactions]
        .filter(t => t.date)
        .sort((a, b) => (a.date < b.date ? -1 : (a.date > b.date ? 1 : 0)));

    const firstYM = sorted[0].date.slice(0, 7);
    const now = new Date();
    const todayYM = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    const lastTxYM = sorted[sorted.length - 1].date.slice(0, 7);
    const lastYM = lastTxYM > todayYM ? lastTxYM : todayYM;

    const months = [];
    let [y, m] = firstYM.split('-').map(Number);
    const [ly, lm] = lastYM.split('-').map(Number);
    while (y < ly || (y === ly && m <= lm)) {
        months.push(`${y}-${String(m).padStart(2, '0')}`);
        m++;
        if (m > 12) { m = 1; y++; }
    }

    let idx = 0;
    let totalRunning = 0;
    const series = [];
    for (const ym of months) {
        const [yy, mm] = ym.split('-').map(Number);
        const daysInMonth = new Date(yy, mm, 0).getDate();
        const monthEndStr = `${yy}-${String(mm).padStart(2, '0')}-${String(daysInMonth).padStart(2, '0')}`;
        while (idx < sorted.length && sorted[idx].date <= monthEndStr) {
            totalRunning += sorted[idx].amount;
            idx++;
        }
        series.push({ month: ym, value: totalRunning });
    }
    netWorthSeriesFull = series;
}

function renderNetWorthHistoryChart() {
    const ctx = document.getElementById('networth-history-chart');
    const fromInput = document.getElementById('networth-range-from');
    const toInput = document.getElementById('networth-range-to');
    if (!ctx || !fromInput || !toInput) return;

    if (netWorthSeriesFull.length === 0) {
        if (netWorthChart) { netWorthChart.destroy(); netWorthChart = null; }
        return;
    }

    const allMonths = netWorthSeriesFull.map(p => p.month);
    const minMonth = allMonths[0], maxMonth = allMonths[allMonths.length - 1];
    fromInput.min = minMonth; fromInput.max = maxMonth;
    toInput.min = minMonth; toInput.max = maxMonth;
    if (!fromInput.value) fromInput.value = minMonth;
    if (!toInput.value) toInput.value = maxMonth;

    const from = fromInput.value, to = toInput.value;
    const sliced = netWorthSeriesFull.filter(p => p.month >= from && p.month <= to);

    if (netWorthChart) {
        netWorthChart.destroy();
        netWorthChart = null;
    }

    netWorthChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sliced.map(p => p.month),
            datasets: [{
                label: 'Majątek netto',
                data: sliced.map(p => p.value),
                borderColor: 'rgba(37, 99, 235, 1)',
                backgroundColor: 'rgba(37, 99, 235, 0.08)',
                fill: true,
                tension: 0.15,
                pointRadius: 0,
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `Majątek netto: ${ctx.parsed.y.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: v => `${Number(v).toLocaleString('pl-PL')} PLN`
                    }
                }
            }
        }
    });
}

document.getElementById('networth-range-from')?.addEventListener('change', renderNetWorthHistoryChart);
document.getElementById('networth-range-to')?.addEventListener('change', renderNetWorthHistoryChart);

function renderDashboardChart() {
    const ctx = document.getElementById('dashboard-chart');
    if (!ctx) return;

    const monthNames = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];

    const nonTransferTx = transactions.filter(t => {
        const cat = categories.find(c => c.name === t.category);
        return !cat || cat.type !== 'transfer';
    });

    let labels, incomeData, expenseData;

    if (dashboardView === 'monthly') {
        const now = new Date();
        const months = [];
        for (let i = 11; i >= 0; i--) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            months.push({ year: d.getFullYear(), month: d.getMonth() + 1, label: `${monthNames[d.getMonth()]} ${d.getFullYear()}` });
        }
        labels = months.map(m => m.label);
        incomeData = months.map(m =>
            nonTransferTx.filter(t => {
                if (!t.date) return false;
                const [ty, tm] = t.date.split('-').map(Number);
                return ty === m.year && tm === m.month && t.amount > 0;
            }).reduce((s, t) => s + t.amount, 0)
        );
        expenseData = months.map(m =>
            nonTransferTx.filter(t => {
                if (!t.date) return false;
                const [ty, tm] = t.date.split('-').map(Number);
                return ty === m.year && tm === m.month && t.amount < 0;
            }).reduce((s, t) => s + Math.abs(t.amount), 0)
        );
    } else {
        const currentYear = new Date().getFullYear();
        const years = Array.from({ length: 5 }, (_, i) => currentYear - 4 + i);
        labels = years.map(String);
        incomeData = years.map(y =>
            nonTransferTx.filter(t => t.date && t.date.startsWith(String(y)) && t.amount > 0)
                .reduce((s, t) => s + t.amount, 0)
        );
        expenseData = years.map(y =>
            nonTransferTx.filter(t => t.date && t.date.startsWith(String(y)) && t.amount < 0)
                .reduce((s, t) => s + Math.abs(t.amount), 0)
        );
    }

    if (dashboardChart) {
        dashboardChart.destroy();
        dashboardChart = null;
    }

    dashboardChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Przychody',
                    data: incomeData,
                    backgroundColor: 'rgba(16, 185, 129, 0.75)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: 'Wydatki',
                    data: expenseData,
                    backgroundColor: 'rgba(244, 63, 94, 0.75)',
                    borderColor: 'rgba(244, 63, 94, 1)',
                    borderWidth: 1,
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} PLN`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: val => `${val.toLocaleString('pl-PL')} PLN` }
                }
            }
        }
    });
}

