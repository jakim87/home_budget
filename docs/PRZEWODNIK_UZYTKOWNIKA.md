# Przewodnik użytkownika — jak efektywnie korzystać z aplikacji

> Ostatnia aktualizacja: 2026-07-12
> Ten dokument tłumaczy działanie aplikacji **prostym językiem**, bez żargonu technicznego — jest pisany dla domowników korzystających z appki, nie dla programistów. Dokumentacja techniczna/biznesowa jest w [DOCUMENTATION.md](DOCUMENTATION.md).

## Spis treści

1. **Pierwsze kroki** ✅
2. Podstawowy cykl pracy: import → weryfikacja → zatwierdzenie *(do uzupełnienia)*
3. **Jak appka rozpoznaje kontrahentów** ✅
4. Kategorie *(do uzupełnienia)*
5. Przelewy wewnętrzne *(do uzupełnienia)*
6. Transakcje cykliczne vs zaplanowane *(do uzupełnienia)*
7. Splity *(do uzupełnienia)*
8. Dashboard i raporty *(do uzupełnienia)*
9. Archiwum i usuwanie *(do uzupełnienia)*
10. FAQ / typowe pułapki *(do uzupełnienia)*

---

## 1. Pierwsze kroki

### Najważniejsza rzecz przed pierwszym importem: skonfiguruj WSZYSTKIE swoje konta

Zanim zaczniesz importować wyciągi z banku, wejdź do zakładki **Słowniki** i **załóż od razu wszystkie konta**, między którymi mogą u Ciebie występować przelewy wewnętrzne — czyli wszystkie Twoje rachunki bankowe, konta oszczędnościowe i portfele gotówkowe, nie tylko to jedno, z którego akurat importujesz wyciąg. Dla każdego konta uzupełnij **numer rachunku** (jeśli je posiada) — to pole jest kluczowe.

**Dlaczego kolejność ma znaczenie:**

Appka rozpoznaje przelew wewnętrzny (czyli przesunięcie pieniędzy między *Twoimi własnymi* kontami) **po numerze rachunku odbiorcy** — i robi to jako **pierwszy, nadrzędny krok** analizy, zanim w ogóle spojrzy na nazwę kontrahenta czy tytuł transakcji. Jeśli w chwili importu docelowe konto **jeszcze nie istnieje** w Słowniku (bo dodasz je dopiero później), appka nie ma jak rozpoznać przelewu jako wewnętrznego — potraktuje go jak zwykłą, "obcą" transakcję (albo poprosi o ręczne przypisanie kontrahenta/kategorii).

**Co to oznacza w praktyce, jeśli zrobisz to w złej kolejności:**
- transakcje zaimportowane *przed* dodaniem drugiego konta **nie zostaną automatycznie naprawione**, nawet gdy to konto dodasz później — trzeba je poprawić ręcznie,
- tylko transakcje zaimportowane *po* dodaniu wszystkich kont będą od razu poprawnie rozpoznane jako „Przelew wewnętrzny”.

**Rada:** jednorazowo, na samym początku korzystania z appki (albo przed importem z nowego banku/konta), poświęć 5 minut i uzupełnij Słownik kont w całości. Oszczędzi Ci to ręcznego poprawiania transakcji później.

---

## 3. Jak appka rozpoznaje kontrahentów

Kiedy importujesz wyciąg z banku, appka próbuje sama zgadnąć, do jakiego kontrahenta (sklepu, osoby, firmy) należy transakcja i jaką kategorię jej przypisać. Żeby dobrze z tego korzystać, warto wiedzieć, **na jakiej podstawie** appka to zgaduje.

### Appka patrzy na DWA pola naraz: tytuł i dane kontrahenta

Każda transakcja z banku ma dwa osobne pola tekstowe:

- **Tytuł** — opis operacji, np. „Płatność BLIK 12.03.2026 Nr transakcji 90000000001 mojeuslugi.przyklad.pl”
- **Dane kontrahenta** — kto (wg banku) odebrał płatność, np. „Autopay S.A. Przykładowa 1 Warszawa”

Appka **łączy oba te pola w jeden tekst** i sprawdza, czy nazwa któregoś zapisanego już kontrahenta pasuje **gdziekolwiek** w tym połączonym tekście — nie tylko w polu „dane kontrahenta”.

To ważne, bo czasem to tytuł zawiera prawdziwą nazwę sklepu, a dane kontrahenta pokazują tylko pośrednika płatności (patrz niżej).

### Dlaczego to ma znaczenie: pośrednicy płatności (BLIK, PayU, Autopay)

Przy płatnościach BLIK-iem bank często wpisuje w polu „dane kontrahenta” **nie sklep, tylko firmę obsługującą płatność** (PayU, Autopay) — a prawdziwa nazwa sklepu ląduje w tytule.

**Przykład poglądowy:**

| Pole | Transakcja 1 (płatność kartą) | Transakcja 2 (płatność BLIK, ten sam sklep) |
|---|---|---|
| Tytuł | Płatność kartą... | ...Nr transakcji 90000000002 **sklep-przyklad.pl** |
| Dane kontrahenta | **sklep-przyklad.pl** Kraków | PayU Adresowa 1 Poznań |

Mimo że w drugiej transakcji pole „dane kontrahenta” jest bezużyteczne (to adres PayU, nie sklepu), appka i tak poprawnie rozpozna sklep — **bo szuka też w tytule**.

### Praktyczna zasada: nazywaj kontrahenta po sklepie, nie po pośredniku

✅ **Rób tak:** nazywaj kontrahenta krótką, rozpoznawalną nazwą sprzedawcy, np. „Play”, „4F”, „Netflix” — czyli tym, co faktycznie kupiłeś.

❌ **Nie rób tak:** nie nazywaj kontrahenta „PayU” albo „Autopay” — to firmy pośredniczące w płatności dla **wielu różnych sklepów jednocześnie**. Gdybyś tak zrobił, appka w przyszłości przypisze do tego samego kontrahenta zupełnie niepowiązane zakupy (bo pole „dane kontrahenta” dla płatności BLIK-iem często wygląda identycznie, niezależnie od tego, co i gdzie kupiłeś).

### Co appka robi krok po kroku (uproszczenie)

1. Sprawdza, czy to przelew między Twoimi własnymi kontami (po numerze rachunku) — jeśli tak, koniec, gotowe.
2. Sprawdza, czy nazwa **istniejącego** kontrahenta pojawia się w połączonym tekście tytuł+dane kontrahenta — jeśli tak, przypisuje ten sam kontrahent i tę samą kategorię co ostatnio.
3. Jeśli nie znajdzie dokładnego dopasowania, próbuje znaleźć **podobną** nazwę (drobne literówki, różnice w zapisie) — ale tylko gdy podobieństwo jest bardzo wysokie.
4. Jeśli nic nie pasuje — appka nie zgaduje na siłę, tylko podpowiada nazwę do zaakceptowania lub poprawienia przy weryfikacji w zakładce „Do weryfikacji”.

### Co zrobić, gdy appka źle dopasuje albo nie dopasuje wcale

To normalne przy zupełnie nowym sklepie/kontrahencie. Przy zatwierdzaniu w zakładce „Do weryfikacji” po prostu popraw nazwę na czystą i krótką (np. „Żabka” zamiast „Żabka Z1234 Warszawa”) — od tego momentu appka będzie rozpoznawać ten sklep poprawnie przy każdej kolejnej transakcji, niezależnie od numeru placówki czy miasta.
