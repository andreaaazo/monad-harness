import { oneLine } from "../format";

/** How much is read before opening: enough for the reason, not for a program's output. */
const SUMMARY = 160;

/**
 * The words of whoever said no, as they were written: one line to get the idea, the whole text on request.
 * A short text has nothing to open.
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
