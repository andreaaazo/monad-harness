# Modifiche agli script QA copiati

Gli script qui accanto sono copie degli originali in `legacy/`. Una copia che differisce dall'originale è elencata
qui, con il motivo; `tests/fixtures/qa_scripts.json` ne tiene gli hash.

## svg_audit.py

- Il tratto ereditato da un `<svg>` o da un `<g>` ora viene segnalato sull'elemento grafico che lo disegna
  (`path`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `text`, `tspan`, `textPath`, `use`).
  `stroke="none"` sul figlio lo interrompe, `inherit` prende il valore del padre.
- Un elemento `<style>` ora produce un avviso, perché i suoi stili non sono verificabili.
- Perché: COR-016. Prima un gruppo con `stroke` passava il controllo e il tratto non espanso arrivava alla consegna.
  Decisione Q4 (docs/audit/SUMMARY.md), Task 2.26: un controllo corretto può trasformare un vecchio PASS in un FAIL,
  ed è giusto così.
