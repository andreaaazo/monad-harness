# ADR-0023: il progetto diventa un SaaS

**Contesto.** `00-PROJECT.md` escludeva un prodotto multi-tenant o un servizio pubblico: il sistema girava su questa macchina, per
questo studio. Il 2026-11-01 Andrea decide che il progetto si espanderà in un SaaS completo, stabile e forte.

**Decisione.** Il SaaS è un obiettivo del progetto, con un traguardo proprio, M7, dopo il primo cliente reale di M6. Questo
rovescia quel non-obiettivo.

Fino a M7 il sistema resta su una macchina, con un operatore. Le scelte nuove non devono però precludere il SaaS: per questo
Django (ADR-0020), casi d'uso separati dagli ingressi e registro dietro una porta (ADR-0021). La multi-tenancy non si costruisce
in anticipo.

**Da decidere prima di M7, con un ADR ciascuna.**
- Isolamento dei dati per cliente, e se il registro passa da SQLite a Postgres: ADR-0001 è scritto per una macchina singola, con
  una sola catena di hash.
- Dove girano i lavori: sandbox, Craft, Blender e GPU oggi stanno su questa macchina (ADR-0005).
- Se le licenze dei Craft permettono l'uso da parte di un servizio.
- Dati del cliente verso l'API: conservazione, regione e contratto.
- A chi si vende, con quali piani e quale fatturazione.

**Conseguenze.** La regola "lo studio non scrive codice di siti e app" resta: riguarda le consegne ai clienti, non il nostro
prodotto. Il rischio di costruire infrastruttura invece di design pesa di più: M7 non inizia finché M6 non ha servito un cliente
reale.
