# Capacità dimostrate

Una capacità entra qui solo dopo essere stata provata su un lavoro, con il risultato guardato e
le misure. Il criterio per aggiungere uno strumento: **quale risultato desiderato oggi non
otteniamo bene?** Poi si verifica quel risultato.

| Capacità | Stato | Prova | Limiti osservati |
|---|---|---|---|
| Render 3D di packaging con grafiche reali (Blender, `pack_render.py`) | dimostrata su scatola 120×60×180 mm | 5 iterazioni guardate: sovraesposto → colore lontano (ΔEok 0.146, 2.4% bruciato) → fedele (ΔEok 0.058, 0% bruciato, finitura opaca) | solo scatole a sei facce; niente fustelle aperte, pieghe, materiali speciali (lamina, rilievo); luce da studio unica |
| Coerenza di un set fotografico (`photo_set.py`) | dimostrata su 4 foto eterogenee | dispersione L 0.082 → 0.045, contrasto 0.073 → 0.023, croma 0.024 → 0.007 | allinea statistiche, non luce e soggetto: una foto notturna resta fuori set (segnalata) |
| Design di interfacce in FigCraft senza finestra | dimostrata su frame di prova | creazione, testo con font della libreria, export e render dei frame, audit con difetti voluti tutti trovati | id dei nodi tra esecuzioni da ricavare dagli esiti; il lavoro ricco passa dall'MCP |
| Design in FigCraft via MCP da un agente | dimostrata (tecnica) | sessione reale: lock → 2 frame 390×844, titolo, testo, pulsante con interazione e slideIn 300 ms → salvataggio → `design_audit` PASS automatico → render guardato → `observe` → ticket DONE | l'agente ha usato il carattere di default (Inter): ora l'audit lo segnala; qualità di design non valutata (prova tecnica) |
| Specimen tipografici dalla libreria | dimostrata | Fraunces e Familjen Grotesk scaricati con licenza, resi sui testi del cliente, usati in FigCraft dopo `--install` | catalogo solo a licenza aperta |
| Logo vettoriale costruito (`logo-design`) | parziale | prova Varco: segno costruito e verificato, idea giudicata debole (REVISE) | la qualità creativa media non è stimata |
| Scoperta del cliente senza tetto di domande | dimostrata al primo giro | sessione reale su una richiesta vaga: 7 temi, ~18 domande concrete, materiali e stimoli chiesti, secondo giro annunciato, `ready` NON ANCORA, nessuna produzione | giri successivi e conferma della comprensione non ancora provati dal vivo |
| Sprint delle direzioni isolate | parziale | 2 sprint: isolamento verificato; convergenza ridotta da leve e libreria | il pre-mortem delle idee ovvie non è ancora provato dal vivo |
| Fotoritocco in PhotoCraft | dimostrata su un'area piccola | riempimento in base al contenuto di una macchia sul tavolo + curva calda; `pixel_diff`: cambiato solo il rettangolo previsto (SSIM 0.996) | a 4× l'area riempita è più morbida della venatura; rimozioni grandi, maschere complesse e compositing non ancora provati |
| Master Craft da CLI, anche in parallelo (`master.py`) | dimostrata (tecnica) | il 2026-10-31: VectorCraft, PhotoCraft, EffectCraft su file separati in parallelo, conversione SVG → `.vectorcraft`, export dal master; sessione reale di `identity-designer`: master costruito con comandi nativi, SVG derivato, ticket consegnato e accettato, firma altrui, immagine grande e autogiudizio bloccati | la qualità del lavoro nativo nel master resta da dimostrare su un progetto reale |
| Prototipi FigCraft con interazioni e smart animate provati su touch | da dimostrare | — | — |
| Tipografia commerciale (proposta, licenza, uso) | da dimostrare | — | dipende dal cliente |

Aggiorna la tabella dopo ogni lavoro che usa una capacità in modo nuovo.
