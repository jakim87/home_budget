// --- PODSUMOWANIE I FILTRY ---
window.applySummaryFilter = function(source) {
    const monthInput = document.getElementById('filter-month');
    const startInput = document.getElementById('filter-start');
    const endInput = document.getElementById('filter-end');

    if (source === 'month') {
        startInput.value = '';
        endInput.value = '';
    } else if (source === 'range') {
        monthInput.value = '';
    }
    renderSummary();
}

function renderSummary() {
    const monthFilter = document.getElementById('filter-month').value;
    const startFilter = document.getElementById('filter-start').value;
    const endFilter = document.getElementById('filter-end').value;

    // Wyświetlenie aktualnego okresu w nowej nawigacji
    const monthNames = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"];
    const summaryDisplay = document.getElementById('summary-month-display');
    if (summaryDisplay) {
        if (monthFilter) {
            const [y, m] = monthFilter.split('-');
            summaryDisplay.innerText = `${monthNames[parseInt(m)-1]} ${y}`;
            summaryDisplay.classList.add('text-blue-600');
        } else if (startFilter || endFilter) {
            summaryDisplay.innerText = `Wybrany zakres dat`;
            summaryDisplay.classList.add('text-blue-600');
        } else {
            summaryDisplay.innerText = `${monthNames[viewDate.getMonth()]} ${viewDate.getFullYear()}`;
            summaryDisplay.classList.remove('text-blue-600');
        }
    }

    // --- AKTUALIZACJA KARTY SALDA ---
    const balanceCard = document.getElementById('summary-account-balance-card');
    if (balanceCard) {
        const balanceTitle = balanceCard.querySelector('h3');
        const balanceValue = document.getElementById('summary-current-balance');
        
        if (globalAccountFilter) {
            // Konto może być aktywne albo nieaktywne (archiwalne) — szukamy w obu.
            const acc = accounts.find(a => a.id == globalAccountFilter)
                || inactiveAccounts.find(a => a.id == globalAccountFilter);
            if (acc) {
                const label = accounts.some(a => a.id == globalAccountFilter) ? acc.name : `${acc.name}, nieaktywne`;
                balanceTitle.innerText = `Bieżące saldo (${label})`;
                balanceValue.innerText = `${Number(acc.balance).toFixed(2)} PLN`;
            }
        } else {
            const totalBalance = accounts.reduce((sum, a) => sum + a.balance, 0);
            balanceTitle.innerText = `Bieżące saldo (wszystkie konta)`;
            balanceValue.innerText = `${totalBalance.toFixed(2)} PLN`;
        }
    }

    const allTx = getFullTransactionsList(monthFilter, startFilter, endFilter);
    let filteredTx = allTx;

    if (monthFilter) {
        const [year, month] = monthFilter.split('-');
        filteredTx = allTx.filter(t => {
                if (!t.date) return false;
                const [tYear, tMonth] = t.date.split('-');
                return parseInt(tYear, 10) === parseInt(year, 10) && parseInt(tMonth, 10) === parseInt(month, 10);
        });
    } else if (startFilter || endFilter) {
        filteredTx = allTx.filter(t => {
            let pass = true;
            if (startFilter && t.date < startFilter) pass = false;
            if (endFilter && t.date > endFilter) pass = false;
            return pass;
        });
    } else {
        filteredTx = allTx.filter(t => isSameMonthAndYear(t.date, viewDate));
    }

    let income = 0;
    let expense = 0;
    let catTotals = {};

    filteredTx.forEach(t => {
        const txCatObj = categories.find(c => c.name === t.category);
        const isTxTransfer = txCatObj && txCatObj.type === 'transfer';

        if (t.splits && t.splits.length > 0) {
            let totalSplitAmt = 0;
            t.splits.forEach(s => {
                const sCatObj = categories.find(c => c.name === s.category);
                const isSplitTransfer = sCatObj && sCatObj.type === 'transfer';

                let actualAmount = t.amount < 0 ? -Math.abs(s.amount) : Math.abs(s.amount);
                totalSplitAmt += Math.abs(actualAmount);
                if (!isSplitTransfer) {
                    if (actualAmount > 0) income += actualAmount; else expense += Math.abs(actualAmount);
                }
                catTotals[s.category] = (catTotals[s.category] || 0) + Math.abs(actualAmount);
            });
            
            let remaining = Math.abs(t.amount) - totalSplitAmt;
            if (remaining > 0.01) {
                let remActual = t.amount < 0 ? -remaining : remaining;
                if (!isTxTransfer) {
                    if (remActual > 0) income += remActual; else expense += Math.abs(remActual);
                }
                catTotals[t.category] = (catTotals[t.category] || 0) + remaining;
            }
        } else {
            if (!isTxTransfer) {
                if (t.amount > 0) income += t.amount; else expense += Math.abs(t.amount);
            }
            catTotals[t.category] = (catTotals[t.category] || 0) + Math.abs(t.amount);
        }
    });

    document.getElementById('summary-income').innerText = `${income.toFixed(2)} PLN`;
    document.getElementById('summary-expense').innerText = `${expense.toFixed(2)} PLN`;
    
    const total = income - expense;
    const totalEl = document.getElementById('summary-total');
    totalEl.innerText = `${total >= 0 ? '+' : ''}${total.toFixed(2)} PLN`;
    totalEl.className = `text-2xl font-bold ${total >= 0 ? 'text-emerald-600' : 'text-rose-600'}`;

    const list = document.getElementById('summary-category-list');
    list.innerHTML = '';
    
    // Grupowanie na przychody i wydatki
    const incCats = Object.keys(catTotals).filter(cat => categories.find(c => c.name === cat)?.type === 'income');
    const expCats = Object.keys(catTotals).filter(cat => categories.find(c => c.name === cat)?.type === 'expense');
    const transCats = Object.keys(catTotals).filter(cat => categories.find(c => c.name === cat)?.type === 'transfer');
    
    // Renderuj Przychody
    if(incCats.length > 0) {
        list.innerHTML += `<tr><td colspan="3" class="bg-emerald-50 text-emerald-700 font-bold p-3 text-xs uppercase tracking-wider">Przychody</td></tr>`;
        incCats.sort((a, b) => catTotals[b] - catTotals[a]).forEach(cat => {
            const percentage = income > 0 ? Math.round((catTotals[cat] / income) * 100) : 0;
            list.innerHTML += buildSummaryRow(cat, catTotals[cat], percentage, 'emerald');
        });
    }

    // Renderuj Wydatki
    if(expCats.length > 0) {
        list.innerHTML += `<tr><td colspan="3" class="bg-rose-50 text-rose-700 font-bold p-3 text-xs uppercase tracking-wider mt-2">Wydatki</td></tr>`;
        expCats.sort((a, b) => catTotals[b] - catTotals[a]).forEach(cat => {
            const percentage = expense > 0 ? Math.round((catTotals[cat] / expense) * 100) : 0;
            list.innerHTML += buildSummaryRow(cat, catTotals[cat], percentage, 'rose');
        });
    }

    // Renderuj Transfery
    if(transCats.length > 0) {
        list.innerHTML += `<tr><td colspan="3" class="bg-sky-50 text-sky-700 font-bold p-3 text-xs uppercase tracking-wider mt-2">Przelewy Wewnętrzne</td></tr>`;
        transCats.sort((a, b) => catTotals[b] - catTotals[a]).forEach(cat => {
            list.innerHTML += buildSummaryRow(cat, catTotals[cat], null, 'sky');
        });
    }
}

function buildSummaryRow(catName, amount, percentage, colorPrefix) {
    const percentageHtml = percentage !== null ? `
        <div class="flex items-center justify-end gap-2">
            <span class="text-xs text-slate-500 w-8 text-right">${percentage}%</span>
            <div class="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-${colorPrefix}-500 rounded-full" style="width: ${percentage}%"></div>
            </div>
        </div>
    ` : `<span class="text-xs text-slate-400 italic flex justify-end">Obojętne dla bilansu</span>`;

    return `
        <tr class="hover:bg-slate-50">
            <td class="p-4 border-b border-slate-100 font-medium text-slate-700">${catName}</td>
            <td class="p-4 border-b border-slate-100 font-bold text-right text-${colorPrefix}-600">${amount.toFixed(2)} PLN</td>
            <td class="p-4 border-b border-slate-100">
                ${percentageHtml}
            </td>
        </tr>
    `;
}

