import type { InstanceView, WaitView } from "../api";
import { counted, minutes, seconds, usd, when } from "../format";
import { between, workScale } from "../timescale";

/**
 * Ogni istanza è una barra, dalla prima all'ultima chiamata, sulla scala del lavoro: le attese del cliente non
 * occupano spazio, hanno una riga loro. Le barre sono solo un aiuto visivo: ciò che dicono è scritto anche in
 * testo, per chi non le vede.
 */
export function Timeline({
  instances,
  waits,
  start,
  end,
}: {
  readonly instances: readonly InstanceView[];
  readonly waits: readonly WaitView[];
  readonly start: string;
  readonly end: string;
}) {
  const place = workScale(start, end, waits);
  // Istanze e attese in ordine di inizio; a pari istante prima l'istanza, che è ciò che l'attesa interrompe.
  const rows = [
    ...instances.map((instance) => ({ at: Date.parse(instance.started_at), order: 0, instance })),
    ...waits.map((wait) => ({ at: Date.parse(wait.started_at), order: 1, wait })),
  ].sort((a, b) => a.at - b.at || a.order - b.order);
  return (
    <ol className="timeline" aria-label="Timeline delle istanze">
      {rows.map((row) =>
        "wait" in row ? (
          <li key={`attesa-${row.wait.ended_at}`} className="wait">
            <span className="label">
              <strong>in attesa del cliente</strong> gate {row.wait.gate}
            </span>
            <span className="track" aria-hidden="true">
              <span className="pause" style={{ left: `${place(row.wait.started_at)}%` }} />
            </span>
            <span className="facts">
              ferma per {minutes(row.wait.minutes)}, dal {when(row.wait.started_at)} al {when(row.wait.ended_at)}
            </span>
          </li>
        ) : (
          <Instance key={row.instance.instance} instance={row.instance} start={start} place={place} />
        ),
      )}
    </ol>
  );
}

function Instance({
  instance,
  start,
  place,
}: {
  readonly instance: InstanceView;
  readonly start: string;
  readonly place: (moment: string) => number;
}) {
  const left = place(instance.started_at);
  const width = Math.max(place(instance.ended_at) - left, 0.8);
  return (
    <li>
      <span className="label">
        <strong>{instance.phase}</strong> {instance.instance}
      </span>
      <span className="track" aria-hidden="true">
        <span className="bar" style={{ left: `${left}%`, width: `${Math.min(width, 100 - left)}%` }} />
      </span>
      <span className="facts">
        da {minutes(between(start, instance.started_at))} per {minutes(between(instance.started_at, instance.ended_at))},{" "}
        {counted(instance.calls, "chiamata", "chiamate")}, {usd(instance.cost_usd)}, modello {seconds(instance.model_ms)}
      </span>
    </li>
  );
}
