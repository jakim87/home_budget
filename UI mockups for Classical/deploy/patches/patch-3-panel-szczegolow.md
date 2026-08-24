# Patch 3 — panel szczegółów operacji

Najbardziej inwazyjny z trzech: wymaga kontenera w `base.html` i nowego
pliku JS. Nie zmienia istniejącej logiki — panel tylko czyta zaznaczoną
operację i zapisuje kategorię oraz komentarz przez te same endpointy,
z których korzysta edycja inline.

## Krok 1: kontener w `base.html`

Tabela historii operacji siedzi w zakładce `#tab-transactions`. Owiń ją
w siatkę dwukolumnową. Znajdź element opakowujący tabelę i zamień na:

```html
<div id="tx-layout" class="grid gap-0 items-start" style="grid-template-columns:1fr 340px">
  <div id="tx-list-col" class="pr-6" style="border-right:1px solid var(--color-divider);min-width:0">
    <!-- ⇩ tu zostaje istniejąca tabela z #transaction-list bez zmian ⇩ -->
  </div>

  <aside id="tx-detail" class="pl-6 pt-4 flex flex-col gap-5">
    <div id="tx-detail-empty" style="color:var(--color-neutral-600);font-size:13px">
      Kliknij operację, aby zobaczyć szczegóły.
    </div>
    <div id="tx-detail-card" class="hidden" style="border:1px solid var(--color-accent);border-radius:4px;padding:16px">
      <div class="flex justify-between items-baseline">
        <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--color-accent)">Zaznaczona operacja</div>
        <span onclick="closeTxDetail()" class="cursor-pointer text-xs" style="color:var(--color-neutral-600)">✕</span>
      </div>
      <h4 id="txd-contractor" style="margin:6px 0 2px;font-size:19px"></h4>
      <div id="txd-amount" class="tabular-nums" style="font-family:var(--font-heading);font-size:29px;margin-bottom:10px"></div>
      <dl id="txd-meta" class="flex flex-col gap-1.5" style="font-size:12.5px"></dl>
      <div id="txd-desc" style="font-size:12px;color:var(--color-neutral-700);margin-top:10px;line-height:1.5"></div>
      <hr style="height:1px;border:0;margin:18px 0;background:var(--color-divider)">
      <label class="block mb-1" style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--color-neutral-600)">Kategoria</label>
      <select id="txd-category" class="w-full p-2 text-sm"></select>
      <label class="block mb-1 mt-3" style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--color-neutral-600)">Komentarz</label>
      <input id="txd-comment" maxlength="255" placeholder="np. plan rodzinny" class="w-full p-2 text-sm">
      <div class="flex gap-2 mt-3">
        <button onclick="saveTxDetail()" class="flex-1 p-2 text-sm bg-blue-600">Zapisz</button>
        <button onclick="openSplitModal(selectedTxId)" class="p-2 text-sm">Rozbij</button>
      </div>
    </div>
  </aside>
</div>
```

Uwaga: `class="bg-blue-600"` na przycisku zostaje celowo — `classical.css`
przerabia go na złoty obrys, więc nie trzeba nowej klasy.

## Krok 2: zwężanie ekranu

Panel na wąskim ekranie schodzi z siatki i wraca jako nakładka po kliknięciu
przycisku. Do `classical.css` (albo `style.css`) dopisz:

```css
@media (max-width: 1240px) {
  #tx-layout { display: block !important; }
  #tx-list-col { padding-right: 0 !important; border-right: none !important; overflow-x: auto; }
  #tx-detail {
    position: fixed; top: 12px; right: 12px; bottom: 12px;
    width: min(340px, calc(100vw - 24px)); z-index: 40;
    overflow-y: auto; padding: 16px;
    background: var(--color-bg);
    border: 1px solid var(--color-divider); border-radius: 4px;
    box-shadow: var(--shadow-lg);
  }
  #tx-detail.collapsed { display: none; }
  #tx-detail-fab { display: inline-flex !important; }
}
#tx-detail-fab { display: none; }
```

I przycisk wywołujący — obok licznika operacji w pasku filtrów:

```html
<button id="tx-detail-fab" onclick="document.getElementById('tx-detail').classList.toggle('collapsed')"
        class="fixed right-5 bottom-5 z-50 p-2.5 text-sm bg-white items-center gap-2"
        style="box-shadow:var(--shadow-md)">
  <span id="tx-detail-dot" style="width:7px;height:7px;border-radius:50%;background:var(--color-accent)"></span>
  Szczegóły operacji
</button>
```

## Krok 3: nowy plik `app/static/js/18_tx_detail.js`

```js
// Panel szczegółów operacji — czyta z tej samej listy co renderTransactions().
let selectedTxId = null;

function selectTx(id) {
    selectedTxId = id;
    renderTxDetail();
    renderTransactions();   // odświeża podświetlenie wiersza
}

function closeTxDetail() {
    selectedTxId = null;
    renderTxDetail();
    renderTransactions();
}

function renderTxDetail() {
    const empty = document.getElementById('tx-detail-empty');
    const card  = document.getElementById('tx-detail-card');
    if (!card) return;

    if (selectedTxId === null) {
        card.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }

    const all = getFullTransactionsList(null, null, null);
    const t = all.find(x => x.id === selectedTxId);
    if (!t) { closeTxDetail(); return; }

    empty.classList.add('hidden');
    card.classList.remove('hidden');

    const isPositive = t.amount >= 0;
    document.getElementById('txd-contractor').innerText = t.contractor_name || t.contractor || '—';
    document.getElementById('txd-amount').innerText =
        `${isPositive ? '+' : '−'}${Math.abs(t.amount).toFixed(2)} PLN`;

    const meta = [
        ['Data', t.date],
        ['Konto', accountLabelById(t.account_id)],
        ['Kategoria', t.category],
        ['Źródło', t.isVirtual ? 'cykliczna' : 'wyciąg / ręcznie']
    ];
    document.getElementById('txd-meta').innerHTML = meta.map(([k, v]) => `
        <div class="flex justify-between gap-2.5">
          <dt style="color:var(--color-neutral-600)">${k}</dt>
          <dd class="tabular-nums m-0 text-right">${escapeHtml(String(v ?? '—'))}</dd>
        </div>`).join('');

    document.getElementById('txd-desc').innerText = t.desc || '';
    document.getElementById('txd-category').innerHTML = getCategoryOptionsHtml(t.category, false);
    document.getElementById('txd-comment').value = t.comment || '';
}

// Zapis idzie tą samą drogą co edycja inline — bez nowego endpointu.
async function saveTxDetail() {
    if (selectedTxId === null) return;
    const payload = {
        category: document.getElementById('txd-category').value,
        comment:  document.getElementById('txd-comment').value
    };
    try {
        const res = await fetch(`/api/transactions/${selectedTxId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(await res.text());
        showToast('Zapisano', 'success');
        await loadTransactions();     // funkcja z 01_state.js
        renderTransactions();
        renderTxDetail();
    } catch (e) {
        showToast('Nie udało się zapisać', 'error');
    }
}

window.selectTx = selectTx;
window.closeTxDetail = closeTxDetail;
window.saveTxDetail = saveTxDetail;
```

**Sprawdź przed wdrożeniem:** metoda i ścieżka w `saveTxDetail` (`PATCH
/api/transactions/<id>`) oraz nazwa `loadTransactions` — weź je z tego, czego
używa `saveInlineEdit()` w `11_transactions.js` (linia 138). Jeśli tam jest
`PUT` albo inny URL, użyj identycznego.

## Krok 4: klikanie wiersza zaznacza operację

W `11_transactions.js`, w **TRYBIE WIDOKU**, przy ustawianiu klasy wiersza:

```js
// przed
row.className = `transition-colors group hover:bg-slate-50 ${isVirtual ? 'bg-indigo-50/30' : ''}`;
// po
const isSelected = (typeof selectedTxId !== 'undefined' && selectedTxId === t.id);
row.className = `transition-colors group cursor-pointer hover:bg-slate-50 ${isVirtual ? 'bg-indigo-50/30' : ''}`;
if (isSelected) {
    row.style.background = 'var(--color-accent-100)';
    row.style.boxShadow = 'inset 3px 0 0 var(--color-accent)';
}
if (!t.isVirtual) row.setAttribute('onclick', `selectTx(${t.id})`);
```

Przyciski akcji w ostatniej kolumnie muszą przestać propagować klik —
dodaj `event.stopPropagation()` w każdym z nich:

```js
onclick="event.stopPropagation(); startInlineEdit(${t.id})"
onclick="event.stopPropagation(); openSplitModal(${t.id})"
onclick="event.stopPropagation(); deleteTransaction(${t.id})"
```

## Kolejność wdrożenia

Patch 3 jest najbardziej ryzykowny — zrób go po 1 i 2, na osobnej gałęzi,
i sprawdź najpierw na jednym koncie z małą liczbą operacji.
