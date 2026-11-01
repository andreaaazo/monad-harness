# ADR-0001: registro su SQLite + SQLModel

**Contesto.** Serve un registro di ticket, eventi e prove, con garanzie forti. Le opzioni erano SQLite con
SQLModel o Kitsu (gazu).

**Decisione.** SQLite con SQLModel, eventi solo in aggiunta (trigger) e catena di hash.

**Perché non Kitsu.** È pensato per il tracking di produzione animazione e VFX: asset, shot, sequenze. Lo
studio lavora soprattutto su brand e 2D, aggiungerebbe un server, e non impone le nostre transizioni né
la catena di prove.

**Conseguenze.** Macchina singola: un solo scrittore per volta, con WAL. Se servirà una vista per persone,
si esporta verso Kitsu o altro; il registro resta qui.
