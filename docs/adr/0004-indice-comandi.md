# ADR-0004: tre strumenti e un indice per i comandi Craft

**Contesto.** I quattro Craft hanno migliaia di comandi. Come tool occuperebbero decine di migliaia di token,
e cambiarli a metà invaliderebbe la cache.

**Decisione.** `craft_search`, `craft_describe`, `craft_run` fissi; indice BM25 + embedding locale,
rigenerato per versione di CLI.

**Alternative.** Il tool search dell'API (`defer_loading`) è valido per i tool, ma qui i comandi sono dati di
una CLI, non funzioni nostre: un indice locale tiene anche validazione ed esecuzione in un punto solo.

**Conseguenze.** I comandi passano da `craft_run`, che li valida contro il catalogo. Un test di contratto
fallisce se una CLI cambia il catalogo senza rigenerare l'indice.
