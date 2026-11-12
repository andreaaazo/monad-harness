import type { Setback } from "../api";
import { counted, when } from "../format";
import { step } from "../labels";
import { Said } from "./said";

/** The steps back in time order, each with the reason written by whoever took it. */
export function SetbackList({ setbacks }: { readonly setbacks: readonly Setback[] }) {
  if (setbacks.length === 0) return <p>Nessun ticket rimandato, bloccato o annullato.</p>;
  return (
    <ol className="setbacks" aria-label="Passi indietro">
      {setbacks.map((item) => (
        <li key={`${item.at}-${item.ticket_id}-${item.action}`}>
          <span className="when">{when(item.at)}</span>
          <div>
            <strong>
              {item.ticket_id} {step(item.action)}
            </strong>{" "}
            da {item.actor}
            {item.after_deliveries > 0 ? ` dopo ${counted(item.after_deliveries, "consegna", "consegne")}` : ""}:{" "}
            {item.title}
            <Said text={item.reason} />
          </div>
          <span className="aside">{item.phase}</span>
        </li>
      ))}
    </ol>
  );
}
