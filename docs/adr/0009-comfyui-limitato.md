# ADR-0009: ComfyUI solo per esplorazione e texture

**Contesto.** Il setup precedente dichiarava "nessun generatore d'immagini". ComfyUI lo cambia. Il default
qui sotto segue la raccomandazione data ad Andrea: si può rivedere.

**Decisione.** Da M4, ComfyUI serve a moodboard, esplorazione di direzioni fotografiche e texture 3D. Mai
per logo, tipografia o asset finali di marca, salvo decisione esplicita di progetto.

**Regole.**
- Container senza uscita di rete, senza ComfyUI-Manager, nodi e pesi bloccati per hash.
- Ogni output è marcato come generato e non può diventare master di una consegna finale.
- Licenza del modello letta sul testo originale prima dell'uso. Le fonti trovate su FLUX.2 si contraddicono.
- Diritti sugli asset generati da verificare con un legale prima di consegnarli a un cliente.

**Conseguenze.** Serve lo scheduler GPU, perché 16 GB di VRAM si dividono con Blender e SigLIP.
