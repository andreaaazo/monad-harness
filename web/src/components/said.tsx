import { oneLine } from "../format";

/** Quanto si legge prima di aprire: abbastanza per il motivo, non per l'uscita di un programma. */
const SUMMARY = 160;

/**
 * Le parole di chi ha detto no, com'erano scritte: una riga per farsi un'idea, il testo intero a richiesta.
 * Un testo corto non ha niente da aprire.
 */
export function Said({ text }: { readonly text: string }) {
  const summary = oneLine(text, SUMMARY);
  if (summary === "") return <p className="aside said">nessun motivo scritto</p>;
  if (summary === text.trim()) return <p className="said">{text.trim()}</p>;
  return (
    <details className="said">
      <summary>{summary}</summary>
      <pre>{text}</pre>
    </details>
  );
}
