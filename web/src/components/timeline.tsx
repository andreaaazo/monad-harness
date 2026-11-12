import type { InstanceView, WaitView } from "../api";
import { counted, minutes, seconds, usd, when } from "../lib/format";
import { between, workScale } from "../lib/timescale";

/**
 * Each instance is a bar, from its first call to its last, on the scale of the work: the client's waits take no
 * space, they have a row of their own. The bars are only a visual aid: what they say is also written as text, for
 * whoever cannot see them.
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
  // Instances and waits in order of start; at the same instant the instance first, as it is what the wait interrupts.
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
