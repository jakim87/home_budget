/* ════════════════════════════════════════════════════════════════════════
   Classical — paleta i typografia wykresów (Chart.js)
   ────────────────────────────────────────────────────────────────────────
   Wdrożenie: skopiuj do app/static/js/00_classical_charts.js
   Numer 00 jest ważny — plik musi się wczytać PRZED 13_dashboard.js
   i 16_reports.js (bootstrap ładuje po nazwie).

   Sam ten plik ustawia domyślne czcionki i siatkę. Kolory serii nadpisz
   według listy w patch-charts.md — literały rgba() w dwóch plikach.
   ══════════════════════════════════════════════════════════════════════ */

const CLASSICAL = {
  accent:      '#b68235',
  accent400:   '#e1ad66',
  accent300:   '#facb8d',
  accent700:   '#7d5411',
  neutral600:  '#7d7979',
  neutral400:  '#bab6b6',
  neutral300:  '#d7d3d3',
  text:        '#201f1d',
  divider:     'rgba(32, 31, 29, 0.16)',
  // Seria kategorii — kolejność od najmocniejszej
  series: ['#b68235', '#e1ad66', '#facb8d', '#7d7979', '#d7d3d3', '#5a3b0a'],
  // Role semantyczne: przychód / wydatek / przelew
  income:   { line: '#7d5411', fill: 'rgba(125, 84, 17, 0.14)' },
  expense:  { line: '#8a5a5a', fill: 'rgba(138, 90, 90, 0.14)' },
  transfer: { line: '#7d7979', fill: 'rgba(125, 121, 121, 0.12)' }
};

if (window.Chart) {
  Chart.defaults.font.family = '"Lora", Georgia, serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = CLASSICAL.neutral600;
  Chart.defaults.borderColor = CLASSICAL.divider;

  // Legenda i tooltipy w tonie systemu — nagłówek szeryfowy, liczby tabularne
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.tooltip.backgroundColor = '#2d2b2b';
  Chart.defaults.plugins.tooltip.borderColor = CLASSICAL.accent700;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 4;
  Chart.defaults.plugins.tooltip.titleFont = { family: '"Cormorant Garamond", Georgia, serif', size: 14, weight: '600' };
  Chart.defaults.plugins.tooltip.bodyFont = { family: '"Lora", Georgia, serif', size: 12 };

  // Siatka: hairline, bez pionowych linii — jak kreski w księdze
  Chart.defaults.scale.grid.color = CLASSICAL.divider;
  Chart.defaults.scale.grid.drawTicks = false;
  Chart.defaults.scale.border = { display: false };
}
