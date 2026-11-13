"use client";

import { type KeyboardEvent, type PointerEvent, type SyntheticEvent, useId, useState } from "react";

import type { Turn } from "../api";
import { area, type Frame, line, nearest, points } from "../lib/chart";
import { count, seconds } from "../lib/format";
import { stop } from "../lib/labels";
import { ScrollRegion } from "./scroll-region";

const FRAME: Frame = { width: 320, height: 96, inset: 6 };
const KEYS = new Set(["ArrowLeft", "ArrowRight", "Home", "End"]);

/**
 * An instance's turns: the context chart and, on request, the table. The turns reach this component only once; the
 * table is built only when it is opened, so a page with hundreds of turns does not carry them three times (HTML,
 * React payload, chart).
 */
export function InstanceTurnsView({
  turns,
  max,
  instance,
  label,
}: {
  readonly turns: readonly Turn[];
  readonly max: number;
  readonly instance: string;
  readonly label: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <ContextChart turns={turns} max={max} label={label} />
      <details onToggle={(event: SyntheticEvent<HTMLDetailsElement>) => setOpen(event.currentTarget.open)}>
        <summary>Turni in tabella</summary>
        {open ? <TurnsTable turns={turns} instance={instance} /> : null}
      </details>
    </>
  );
}

function TurnsTable({ turns, instance }: { readonly turns: readonly Turn[]; readonly instance: string }) {
  return (
    <ScrollRegion label={`Turni di ${instance}`}>
      <table aria-label={`Turni di ${instance}`}>
        <thead>
          <tr>
            <th scope="col" className="number">
              Turno
            </th>
            <th scope="col" className="number">
              Contesto
            </th>
            <th scope="col" className="number">
              Cache letta
            </th>
            <th scope="col" className="number">
              Output
            </th>
            <th scope="col" className="number">
              Durata
            </th>
            <th scope="col" className="number">
              TTFT
            </th>
            <th scope="col">Fine</th>
          </tr>
        </thead>
        <tbody>
          {turns.map((turn, index) => (
            <tr key={turn.seq}>
              <th scope="row" className="number">
                {index + 1}
              </th>
              <td className="number">{count(turn.context)}</td>
              <td className="number">{count(turn.cache_read_tokens)}</td>
              <td className="number">{count(turn.output_tokens)}</td>
              <td className="number">{seconds(turn.duration_ms)}</td>
              <td className="number">{seconds(turn.ttft_ms)}</td>
              <td>{turn.stop_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

/**
 * An instance's context turn by turn, on the shared scale `max`. The pointer, or the arrow keys once the chart has
 * focus, show one turn. Everything it shows is also in the turns table.
 */
function ContextChart({
  turns,
  max,
  label,
}: {
  readonly turns: readonly Turn[];
  readonly max: number;
  readonly label: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const tip = useId();
  const series = points(
    turns.map((turn) => turn.context),
    max,
    FRAME,
  );
  const last = series.at(-1);
  const turn = active === null ? undefined : turns[active];
  const point = active === null ? undefined : series[active];

  const pick = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width > 0) setActive(nearest(((event.clientX - box.left) / box.width) * FRAME.width, turns.length, FRAME));
  };
  const walk = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!KEYS.has(event.key)) return;
    event.preventDefault();
    const end = turns.length - 1;
    const from = active ?? end;
    const to =
      event.key === "Home" ? 0 : event.key === "End" ? end : from + (event.key === "ArrowRight" ? 1 : -1);
    setActive(Math.min(Math.max(to, 0), end));
  };

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${FRAME.width} ${FRAME.height}`}
        role="img"
        aria-label={label}
        aria-describedby={turn ? tip : undefined}
        tabIndex={0}
        onPointerMove={pick}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive(turns.length - 1)}
        onBlur={() => setActive(null)}
        onKeyDown={walk}
      >
        <line
          className="baseline"
          x1={FRAME.inset}
          x2={FRAME.width - FRAME.inset}
          y1={FRAME.height - FRAME.inset}
          y2={FRAME.height - FRAME.inset}
        />
        <path className="wash" d={area(series, FRAME)} />
        <path className="trace" d={line(series)} />
        {point ? (
          <line className="crosshair" x1={point.x} x2={point.x} y1={FRAME.inset} y2={FRAME.height - FRAME.inset} />
        ) : null}
        {last && !point ? <circle className="dot" cx={last.x} cy={last.y} r={4} /> : null}
        {point ? <circle className="dot" cx={point.x} cy={point.y} r={4} /> : null}
      </svg>
      {turn && point ? (
        <div
          id={tip}
          className={`tip${point.x > FRAME.width * 0.6 ? " left" : ""}`}
          style={{ left: `${(point.x / FRAME.width) * 100}%` }}
          role="status"
        >
          <strong>{count(turn.context)} token</strong>
          <span>
            turno {active === null ? "" : active + 1} di {turns.length}
          </span>
          <span>
            cache letta {count(turn.cache_read_tokens)}, output {count(turn.output_tokens)}
          </span>
          <span>
            durata {seconds(turn.duration_ms)}, TTFT {seconds(turn.ttft_ms)}
          </span>
          <span>fine: {stop(turn.stop_reason)}</span>
        </div>
      ) : null}
    </div>
  );
}
