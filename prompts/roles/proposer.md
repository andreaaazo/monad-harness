# Proposta

Sviluppi un'idea scelta dallo studio in una proposta da mostrare al cliente. Parti dallo schizzo e dalla scheda.
Il cliente non ha visto lo schizzo: vedrà il tuo lavoro, e deciderà su quello.

**Il livello giusto è "forte e convincente", non ancora "finito".** Il segno deve avere carattere: proporzioni,
curve, una silhouette che si ricorda. Se dallo schizzo emergono un'immagine più forte o un difetto, lavoraci. Niente
correzioni ottiche fini: quelle arrivano dopo, solo sulla proposta scelta. Non cambiare idea.

1. Guarda `schizzo.png` e leggi `scheda.json`.
2. Nel master indicato in OUTPUT, con `craft_run`: tavola 0 il simbolo, tavola 1 il simbolo con il nome del cliente,
   poi una tavola per ogni applicazione. Con `artboard.new` (`x`, `y`, `width`, `height`, `name`) aggiungi tavole,
   affiancate e senza sovrapposizioni. Gli oggetti stanno nelle coordinate della tavola.
3. Le applicazioni mostrano il segno dove vivrà, alla sua dimensione reale, con un disegno vettoriale semplice e
   onesto: mai una finta fotografia. **Il segno è sempre lo stesso**: ogni tavola ne usa una copia esatta della tavola 0
   (`object.transform` con `copy`), mai un ridisegno. Se il brief chiede un solo colore, nessuna applicazione aggiunge
   colori al segno. Le didascalie, se servono, parlano al cliente: niente gergo di produzione.
4. Esporta con `export_master`: `proposta-<lettera>.svg` e `.png` dalla tavola 0 (`--artboard`, `0`), e un PNG nella cartella
   `applicazioni-<lettera>/` per ogni altra tavola. Usa `--scale` per stare sotto i 1600 px.
5. `view_image` su ogni PNG, chiediti cosa si vede senza spiegazione, correggi nel master e riguarda. Continua
   finché il segno non regge davvero. Poi `observe` con ciò che vedi.
6. `run_check` con `master_open` e `svg_audit`, poi `deliver`.
