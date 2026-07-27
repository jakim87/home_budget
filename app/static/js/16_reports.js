// =============================================
// ZAKŁADKA: RAPORTY
// =============================================

let rptInitialized = false;
let rptBarChart = null;
let rptLineChart = null;
let rptTableSort = { field: 'date', dir: 'desc' };
let rptFilteredTxs = [];
let rptHiddenTransfers = [];
const RPT_TABLE_MAX = 100;

const RPT_MONTH_NAMES = { '01': 'Sty', '02': 'Lut', '03': 'Mar', '04': 'Kwi', '05': 'Maj', '06': 'Cze', '07': 'Lip', '08': 'Sie', '09': 'Wrz', '10': 'Paź', '11': 'Lis', '12': 'Gru' };

function renderReports() {
    if (!rptInitialized) {
        rptInitDropdowns();
        const excludeChk = document.getElementById('rpt-exclude-transfers');
        if (excludeChk) excludeChk.checked = true;
        rptSetPreset('6months');
        rptInitialized = true;
    } else {
        applyRptFilters();
    }
}

function rptInitDropdowns() {
    // Konta
    const accList = document.getElementById('rpt-accounts-list');
    if (accList) {
        accList.innerHTML = accounts.map(a => `
            <label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 cursor-pointer text-sm text-slate-700">
                <input type="checkbox" class="rpt-acc-check rounded text-blue-600 focus:ring-blue-400 border-slate-300 cursor-pointer" value="${a.id}" checked onchange="applyRptFilters()">
                <span class="flex-1">${a.name}</span>
                <span class="text-xs text-slate-400">${a.bank_name || ''}</span>
            </label>`).join('');
    }

    // Kategorie — grupowane
    const catList = document.getElementById('rpt-categories-list');
    if (catList) {
        const typeLabels = { income: 'Przychody', expense: 'Wydatki', transfer: 'Transfery', system_reconciliation: 'Systemowe' };
        const grouped = {};
        categories.forEach(c => { (grouped[c.type] = grouped[c.type] || []).push(c); });
        let html = '';
        ['income', 'expense', 'transfer', 'system_reconciliation'].forEach(type => {
            if (!grouped[type]) return;
            html += `<p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-2 mb-1 px-1">${typeLabels[type] || type}</p>`;
            grouped[type].forEach(c => {
                const dimmed = (type === 'transfer' || type === 'system_reconciliation') ? 'text-slate-400' : 'text-slate-700';
                html += `<label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 cursor-pointer text-sm ${dimmed}">
                    <input type="checkbox" class="rpt-cat-check rounded text-blue-600 focus:ring-blue-400 border-slate-300 cursor-pointer" value="${c.id}" onchange="applyRptFilters()">
                    <span>${c.name}</span>
                </label>`;
            });
        });
        catList.innerHTML = html;
        // Zaznacz domyślnie tylko income i expense
        document.querySelectorAll('.rpt-cat-check').forEach(chk => {
            const cat = categories.find(c => c.id == parseInt(chk.value));
            chk.checked = cat && (cat.type === 'income' || cat.type === 'expense');
        });
    }

    // Kontrahenci
    const contList = document.getElementById('rpt-contractors-list');
    if (contList) {
        contList.innerHTML = contractors.map(c => `
            <label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 cursor-pointer text-sm text-slate-700 rpt-cont-row" data-name="${c.name.toLowerCase()}">
                <input type="checkbox" class="rpt-cont-check rounded text-blue-600 focus:ring-blue-400 border-slate-300 cursor-pointer" value="${c.id}" checked onchange="applyRptFilters()">
                <span>${c.name}</span>
            </label>`).join('') || '<p class="text-xs text-slate-400 p-2">Brak kontrahentów</p>';
    }
}

function toggleRptDropdown(name) {
    ['accounts', 'categories', 'contractors'].forEach(p => {
        const panel = document.getElementById(`rpt-${p}-panel`);
        if (p === name) panel?.classList.toggle('hidden');
        else panel?.classList.add('hidden');
    });
}

document.addEventListener('click', function(e) {
    if (!e.target.closest('.rpt-dropdown-wrap')) {
        ['accounts', 'categories', 'contractors'].forEach(p => {
            document.getElementById(`rpt-${p}-panel`)?.classList.add('hidden');
        });
    }
});

const RPT_CLASS_MAP = { accounts: 'rpt-acc-check', categories: 'rpt-cat-check', contractors: 'rpt-cont-check' };

function rptSelectAll(type, checked) {
    document.querySelectorAll(`.${RPT_CLASS_MAP[type]}:not([style*="display: none"])`).forEach(chk => { chk.checked = checked; });
    applyRptFilters();
}

function rptToggleExcludeTransfers() {
    applyRptFilters();
}

function rptFilterContractors() {
    const search = (document.getElementById('rpt-contractors-search')?.value || '').toLowerCase();
    document.querySelectorAll('.rpt-cont-row').forEach(row => {
        row.style.display = row.dataset.name.includes(search) ? '' : 'none';
    });
}

function rptLocalDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function rptSetPreset(preset) {
    const now = new Date();
    let from;
    const to = rptLocalDate(now);
    if (preset === 'month') {
        from = rptLocalDate(new Date(now.getFullYear(), now.getMonth(), 1));
    } else if (preset === '3months') {
        from = rptLocalDate(new Date(now.getFullYear(), now.getMonth() - 3, 1));
    } else if (preset === '6months') {
        from = rptLocalDate(new Date(now.getFullYear(), now.getMonth() - 6, 1));
    } else {
        from = rptLocalDate(new Date(now.getFullYear(), 0, 1));
    }
    const fromEl = document.getElementById('rpt-date-from');
    const toEl = document.getElementById('rpt-date-to');
    if (fromEl) fromEl.value = from;
    if (toEl) toEl.value = to;
    applyRptFilters();
}

function resetRptFilters() {
    document.querySelectorAll('.rpt-acc-check, .rpt-cont-check').forEach(chk => { chk.checked = true; });
    document.querySelectorAll('.rpt-cat-check').forEach(chk => {
        const cat = categories.find(c => c.id == parseInt(chk.value));
        chk.checked = cat && (cat.type === 'income' || cat.type === 'expense');
    });
    const excludeChk = document.getElementById('rpt-exclude-transfers');
    if (excludeChk) excludeChk.checked = true;
    rptSetPreset('6months');
}

function applyRptFilters() {
    const dateFrom = document.getElementById('rpt-date-from')?.value || null;
    const dateTo = document.getElementById('rpt-date-to')?.value || null;
    const excludeTransfers = document.getElementById('rpt-exclude-transfers')?.checked ?? true;

    const checkedAccIds = new Set([...document.querySelectorAll('.rpt-acc-check:checked')].map(c => parseInt(c.value)));
    const checkedCatIds = new Set([...document.querySelectorAll('.rpt-cat-check:checked')].map(c => parseInt(c.value)));
    const checkedContIds = new Set([...document.querySelectorAll('.rpt-cont-check:checked')].map(c => parseInt(c.value)));

    const totalAccs = document.querySelectorAll('.rpt-acc-check').length;
    const totalCats = document.querySelectorAll('.rpt-cat-check').length;
    const totalConts = document.querySelectorAll('.rpt-cont-check').length;

    // Odznaczki na przyciskach filtrów
    const accBadge = document.getElementById('rpt-accounts-badge');
    if (checkedAccIds.size < totalAccs) {
        accBadge.textContent = `${checkedAccIds.size}/${totalAccs}`;
        accBadge.classList.remove('hidden');
    } else { accBadge.classList.add('hidden'); }

    const catBadge = document.getElementById('rpt-categories-badge');
    if (excludeTransfers || checkedCatIds.size < totalCats) {
        catBadge.classList.remove('hidden');
    } else { catBadge.classList.add('hidden'); }

    const contBadge = document.getElementById('rpt-contractors-badge');
    if (checkedContIds.size < totalConts) {
        contBadge.textContent = `${checkedContIds.size}/${totalConts}`;
        contBadge.classList.remove('hidden');
    } else { contBadge.classList.add('hidden'); }

    // Filtrowanie transakcji
    rptFilteredTxs = transactions.filter(tx => {
        if (checkedAccIds.size < totalAccs && !checkedAccIds.has(tx.account_id)) return false;
        if (dateFrom && tx.date < dateFrom) return false;
        if (dateTo && tx.date > dateTo) return false;
        const cat = categories.find(c => c.name === tx.category);
        if (excludeTransfers && cat?.type === 'transfer') return false;
        if (cat && checkedCatIds.size < totalCats && !checkedCatIds.has(cat.id)) return false;
        if (tx.contractor_id && checkedContIds.size < totalConts && !checkedContIds.has(tx.contractor_id)) return false;
        return true;
    });

    rptHiddenTransfers = excludeTransfers ? transactions.filter(tx => {
        if (dateFrom && tx.date < dateFrom) return false;
        if (dateTo && tx.date > dateTo) return false;
        const cat = categories.find(c => c.name === tx.category);
        return cat?.type === 'transfer';
    }) : [];

    renderRptKPIs();
    renderRptBarChart();
    renderRptLineChart();
    renderRptTable();
}

function rptFmt(v, showSign = false) {
    const abs = Math.abs(v).toFixed(2).replace('.', ',');
    if (showSign) return `${v >= 0 ? '+' : '−'}${abs} PLN`;
    return `${abs} PLN`;
}

function renderRptKPIs() {
    const income = rptFilteredTxs.filter(t => t.amount > 0);
    const expense = rptFilteredTxs.filter(t => t.amount < 0);
    const incomeSum = income.reduce((s, t) => s + t.amount, 0);
    const expenseSum = expense.reduce((s, t) => s + t.amount, 0);
    const net = incomeSum + expenseSum;
    const transferSum = rptHiddenTransfers.reduce((s, t) => s + t.amount, 0);

    document.getElementById('rpt-kpi-income').textContent = rptFmt(incomeSum);
    document.getElementById('rpt-kpi-income-count').textContent = `${income.length} transakcji`;
    document.getElementById('rpt-kpi-expense').textContent = rptFmt(expenseSum);
    document.getElementById('rpt-kpi-expense-count').textContent = `${expense.length} transakcji`;

    const netEl = document.getElementById('rpt-kpi-net');
    netEl.textContent = rptFmt(net, true);
    netEl.className = `text-2xl font-bold ${net >= 0 ? 'text-emerald-600' : 'text-rose-600'}`;

    document.getElementById('rpt-kpi-transfers').textContent = rptFmt(transferSum, true);
    document.getElementById('rpt-kpi-transfers-count').textContent = `${rptHiddenTransfers.length} transakcji`;
}

function rptGroupByMonth(txs) {
    const months = {};
    txs.forEach(tx => {
        const m = tx.date.substring(0, 7);
        if (!months[m]) months[m] = { income: 0, expense: 0 };
        if (tx.amount > 0) months[m].income += tx.amount;
        else months[m].expense += Math.abs(tx.amount);
    });
    return months;
}

function rptMonthLabel(ym) {
    const [y, m] = ym.split('-');
    return `${RPT_MONTH_NAMES[m]} ${y}`;
}

function renderRptBarChart() {
    const ctx = document.getElementById('rpt-bar-chart');
    if (!ctx) return;
    const months = rptGroupByMonth(rptFilteredTxs);
    const labels = Object.keys(months).sort();

    if (rptBarChart) rptBarChart.destroy();
    rptBarChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.map(rptMonthLabel),
            datasets: [
                {
                    label: 'Przychody',
                    data: labels.map(m => parseFloat(months[m].income.toFixed(2))),
                    backgroundColor: 'rgba(16,185,129,0.75)',
                    borderColor: 'rgb(16,185,129)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Wydatki',
                    data: labels.map(m => parseFloat(months[m].expense.toFixed(2))),
                    backgroundColor: 'rgba(239,68,68,0.75)',
                    borderColor: 'rgb(239,68,68)',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { font: { size: 12 }, boxWidth: 12 } },
                tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.raw.toFixed(2)} PLN` } }
            },
            scales: {
                y: { beginAtZero: true, ticks: { callback: v => `${v} PLN` } }
            }
        }
    });
}

function renderRptLineChart() {
    const ctx = document.getElementById('rpt-line-chart');
    if (!ctx) return;
    const months = rptGroupByMonth(rptFilteredTxs);
    const labels = Object.keys(months).sort();
    const monthlyNet = labels.map(m => parseFloat((months[m].income - months[m].expense).toFixed(2)));
    let cum = 0;
    const cumNet = monthlyNet.map(v => parseFloat((cum += v, cum).toFixed(2)));

    if (rptLineChart) rptLineChart.destroy();
    rptLineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(rptMonthLabel),
            datasets: [
                {
                    label: 'Narastająco',
                    data: cumNet,
                    borderColor: 'rgb(139,92,246)',
                    backgroundColor: 'rgba(139,92,246,0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Bilans miesięczny',
                    data: monthlyNet,
                    borderColor: 'rgb(59,130,246)',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { font: { size: 12 }, boxWidth: 12 } },
                tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.raw.toFixed(2)} PLN` } }
            },
            scales: {
                y: { ticks: { callback: v => `${v} PLN` } }
            }
        }
    });
}

function rptSortTable(field) {
    if (rptTableSort.field === field) {
        rptTableSort.dir = rptTableSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
        rptTableSort.field = field;
        rptTableSort.dir = 'desc';
    }
    ['date', 'amount'].forEach(f => {
        const icon = document.getElementById(`rpt-sort-${f}`);
        if (!icon) return;
        icon.textContent = f === rptTableSort.field ? (rptTableSort.dir === 'asc' ? '↑' : '↓') : '↕';
    });
    renderRptTable();
}

function renderRptTable() {
    const tbody = document.getElementById('rpt-table-body');
    if (!tbody) return;
    const search = (document.getElementById('rpt-table-search')?.value || '').toLowerCase();
    const accMap = Object.fromEntries(accounts.map(a => [a.id, a.name]));

    let txs = rptFilteredTxs.filter(tx => {
        if (!search) return true;
        return (tx.desc || '').toLowerCase().includes(search)
            || (tx.contractor_name || '').toLowerCase().includes(search)
            || (tx.category || '').toLowerCase().includes(search)
            || (accMap[tx.account_id] || '').toLowerCase().includes(search);
    });

    txs = [...txs].sort((a, b) => {
        const va = rptTableSort.field === 'date' ? a.date : a.amount;
        const vb = rptTableSort.field === 'date' ? b.date : b.amount;
        return rptTableSort.dir === 'asc' ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
    });

    const countEl = document.getElementById('rpt-table-count');
    if (countEl) countEl.textContent = `(${txs.length})`;

    const visible = txs.slice(0, RPT_TABLE_MAX);
    const catTypeMap = Object.fromEntries(categories.map(c => [c.name, c.type]));

    tbody.innerHTML = visible.map(tx => {
        const amtClass = tx.amount >= 0 ? 'text-emerald-600' : 'text-rose-600';
        const amtSign = tx.amount >= 0 ? '+' : '';
        const amtText = `${amtSign}${tx.amount.toFixed(2).replace('.', ',')} PLN`;
        const catType = catTypeMap[tx.category];
        const catBadge = catType === 'transfer' ? 'bg-amber-50 text-amber-700 border-amber-200'
                       : catType === 'income'   ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                : 'bg-slate-50 text-slate-600 border-slate-200';
        return `<tr class="hover:bg-slate-50 transition-colors">
            <td class="p-4 text-sm text-slate-500 whitespace-nowrap">${tx.date}</td>
            <td class="p-4 text-sm text-slate-800 max-w-xs">
                <span class="block truncate" title="${tx.desc}">${tx.desc}</span>
                ${tx.comment ? `<span class="text-xs text-slate-400 truncate block" title="${tx.comment}">${tx.comment}</span>` : ''}
            </td>
            <td class="p-4 text-sm text-slate-600 max-w-[160px]">
                <span class="block truncate">${tx.contractor_name || '<span class="text-slate-300">—</span>'}</span>
            </td>
            <td class="p-4">
                <span class="text-xs px-2 py-0.5 rounded-full font-medium border ${catBadge}">${tx.category}</span>
            </td>
            <td class="p-4 text-sm text-slate-500 whitespace-nowrap">${accMap[tx.account_id] || '—'}</td>
            <td class="p-4 text-sm font-semibold ${amtClass} text-right whitespace-nowrap">${amtText}</td>
        </tr>`;
    }).join('') || `<tr><td colspan="6" class="p-10 text-center text-slate-400 text-sm">Brak transakcji spełniających kryteria filtrów.</td></tr>`;

    if (txs.length > RPT_TABLE_MAX) {
        tbody.innerHTML += `<tr><td colspan="6" class="p-3 text-center text-xs text-slate-400 bg-slate-50">Pokazuję ${RPT_TABLE_MAX} z ${txs.length} wierszy — zawęź wyszukiwanie aby zobaczyć pozostałe ${txs.length - RPT_TABLE_MAX}.</td></tr>`;
    }
}