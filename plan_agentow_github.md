# Plan pracy: potok 4 agentów nad zadaniami z GitHub (home_budget)

Repo: `jakim87/home_budget`. Cel: zamienić zgłaszanie i rozwiązywanie issues z GitHuba w powtarzalny proces, gdzie każde zadanie przechodzi przez cztery wyspecjalizowane role, zanim trafi do mergowania.

## Zastrzeżenie

Connector GitHub (`plugin:engineering:github`) nie jest jeszcze autoryzowany w tej sesji — żeby agenci mogli sami czytać/aktualizować issues i PR-y, trzeba go połączyć w ustawieniach Cowork (connector settings) albo w interaktywnej sesji przez `/mcp`. Bez tego mogę pracować tylko na numerze/treści issue, którą mi wkleisz.

## Przepływ pracy

1. Wybierasz issue z GitHuba (numer + treść, albo link).
2. **Agent 1 (Analityk)** analizuje zadanie względem obecnego kodu, proponuje rozwiązanie + plan zmian i **na końcu klasyfikuje ryzyko: niskie albo wysokie** (patrz Triaż niżej).
3. **Triaż:**
   - Ryzyko **wysokie** → plan idzie do Agenta 2 (Security Reviewer), który krytykuje go pod kątem bezpieczeństwa. Jeśli odrzuca — wraca do punktu 2 z listą zastrzeżeń.
   - Ryzyko **niskie** → pomijasz Agenta 2, plan idzie prosto do zatwierdzenia (punkt 4).
4. Ty zatwierdzasz plan (checkpoint) — to jedyny moment, w którym coś trafia do implementacji.
5. **Agent 3 (Implementer)** wdraża zaakceptowane rozwiązanie: model → serwis → blueprint → migracja, branch + PR.
6. **Agent 4 (Tester)** pisze/uruchamia testy, raportuje wynik. Jeśli fail — wraca do punktu 5.
7. Ty robisz finalny review PR i mergujesz.

Każdy agent dostaje na wejściu **tylko wynik poprzedniego** (numer issue, plan, diff, wynik testów) — nie całą historię rozmowy — żeby uniknąć dryfu kontekstu.

### Kryteria triażu (kiedy ryzyko jest wysokie)

Issue jest **wysokiego ryzyka** — zawsze przez Security Reviewera — jeśli dotyka choć jednego z:

- kwot pieniężnych (Decimal, salda, sumy),
- autoryzacji / dostępu do danych innego użytkownika,
- migracji bazy danych,
- importu/parsowania danych zewnętrznych (CSV, inne banki),
- przelewów wewnętrznych (dopasowanie po nazwie kontrahenta).

Wszystko inne (UI, teksty, style, dokumentacja, drobne refaktoryzacje bez zmiany logiki) — **niskie ryzyko**, prosto do Implementera po Twoim zatwierdzeniu.

---

---

## Agenci

Definicje (prompt, narzędzia) żyją w `.claude/agents/` — tu tylko przepływ:

| Krok | Agent | Plik | Definition of done |
|------|-------|------|--------------------|
| 2 | Analityk | `analityk-zadan.md` | plan konkretny (nazwy plików, funkcji), jawne „nie wiem” zamiast zgadywania |
| 3 | Recenzent bezpieczeństwa | `security-reviewer.md` | każdy zarzut wskazuje plik/funkcję i konkretną poprawkę |
| 5 | Implementer | `implementer.md` | kod odpowiada planowi 1:1, PR linkuje issue, migracja przejrzana ręcznie |
| 6 | Tester | `tester.md` | pełny `pytest` przechodzi, przypadki brzegowe finansowe opisane |
