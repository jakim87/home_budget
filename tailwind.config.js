// Tailwind budowany lokalnie (zamiast skryptu z cdn.tailwindcss.com), żeby przeglądarka nie wysyłała
// adresu IP zewnętrznemu dostawcy. Po dodaniu nowej klasy w szablonie albo module JS: `npm run build:css`
// i commit app/static/tailwind.css — serwer nie buduje niczego sam, a CI sprawdza, czy plik jest aktualny.
// Klasy sklejane w locie (np. 'bg-' + kolor) nie zostaną znalezione — pisz pełne nazwy.
module.exports = {
  content: ['./app/templates/**/*.html', './app/static/js/**/*.js'],
};
