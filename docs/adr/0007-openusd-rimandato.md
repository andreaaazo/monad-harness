# ADR-0007: master nativi, OpenUSD rimandato

**Contesto.** OpenUSD è lo standard per scene 3D scambiate tra software.

**Decisione.** Il master 3D resta `.blend`. Non si adotta OpenUSD ora; il modello di scena è un JSON comune
per tutti i mezzi.

**Perché.** Il 3D è una parte piccola del lavoro, e c'è un solo software 3D. La maggior parte dei master è 2D,
dove OpenUSD non si applica.

**Quando rivedere.** Se entra un secondo strumento 3D, o se i clienti chiedono consegne USD.
