import type { Metadata } from "next";
import Link from "next/link";

import type { Measured, ReplayReport, ReplayTool, ReplayTurn } from "../../../../../api";
import { ApiError, api, browserPaths } from "../../../../../api/client";
import { readForPage } from "../../../../../api/read";
import { ProjectHeader } from "../../../../../components/project-header";
import { Said } from "../../../../../components/said";
import { Unavailable } from "../../../../../components/unavailable";
import { count, counted, seconds, usd } from "../../../../../lib/format";
import { outcome, stop } from "../../../../../lib/labels";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: PageProps<"/projects/[name]/replay/[instance]">): Promise<Metadata> {
  const { name, instance } = await params;
  return { title: `${name}: ${instance}` };
}

const ALIGNMENTS: Readonly<Record<ReplayReport["alignment"], string>> = {
  "per richiesta": "ogni turno è legato alla sua chiamata dal request_id",
  "per ordine": "turni e chiamate legati per ordine, tolte le risposte che il motore scarta",
  nessuna: "turni e chiamate non si allineano: le misure dei turni non si mostrano",
};

/** The replay view: an instance turn by turn, with each call's measures and the images. */
export default async function Replay({ params }: PageProps<"/projects/[name]/replay/[instance]">) {
  const { name, instance } = await params;
  const report = await readForPage(() => api.replay(name, instance));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  return (
    <>
      <ProjectHeader project={report.project} view="replay" />
      <p>
        <Link href={`/projects/${encodeURIComponent(report.project)}/replay`}>Tutte le istanze</Link>
      </p>
      <h2>
        <strong>{report.phase}</strong> {report.instance}
      </h2>
      <dl className="summary" aria-label="L'istanza">
        <div>
          <dt>Chi e su cosa</dt>
          <dd>
            {report.role || "–"}
            <span className="aside"> ticket {report.ticket_id || "–"}</span>
          </dd>
        </div>
        <div>
          <dt>Chiamate</dt>
          <dd>
            {count(report.calls)}
            <span className="aside">
              {" "}
              {usd(report.cost_usd)}, {counted(report.turns.length, "turno", "turni")} in trascrizione
            </span>
          </dd>
        </div>
        <div>
          <dt>Esito</dt>
          <dd>
            {outcome(report.outcome_state)}
            <span className="aside"> {counted(report.images, "immagine", "immagini")} viste</span>
          </dd>
        </div>
      </dl>
      <p className="aside">Misure: {ALIGNMENTS[report.alignment]}.</p>
      {report.outcome_note !== "" ? <Said text={report.outcome_note} /> : null}
      {report.unreadable > 0 ? (
        <p className="back">{counted(report.unreadable, "riga illeggibile", "righe illeggibili")} nella trascrizione.</p>
      ) : null}
      <details className="group">
        <summary>Il compito, come lo ha ricevuto l&apos;istanza</summary>
        <pre className="text">{report.task}</pre>
      </details>
      <ol className="turns" aria-label="Turni">
        {report.turns.map((turn) => (
          <Turn key={turn.number} turn={turn} report={report} />
        ))}
      </ol>
      {report.trailing_discarded.length > 0 ? (
        <section aria-label="Dopo l'ultimo turno">
          {report.trailing_discarded.map((item) => (
            <Discarded key={item.seq} item={item} />
          ))}
        </section>
      ) : null}
    </>
  );
}

function measures(item: Measured): string {
  return [
    `${count(item.context)} token di contesto`,
    usd(item.cost_usd),
    item.duration_ms === null ? "durata non misurata" : seconds(item.duration_ms),
    item.stop_reason,
  ].join(" · ");
}

function Discarded({ item }: { readonly item: Measured }) {
  return (
    <p className="back discarded">
      Una risposta scartata: {stop(item.stop_reason)}, {usd(item.cost_usd)}. Non è in trascrizione.
    </p>
  );
}

function Turn({ turn, report }: { readonly turn: ReplayTurn; readonly report: ReplayReport }) {
  return (
    <li className="turn" aria-label={`Turno ${turn.number}`}>
      {turn.discarded.map((item) => (
        <Discarded key={item.seq} item={item} />
      ))}
      <h3>
        Turno {turn.number}
        {turn.measured !== null ? <span className="aside"> {measures(turn.measured)}</span> : null}
      </h3>
      {turn.thinking.length > 0 ? (
        <details className="thinking">
          <summary>Ragionamento</summary>
          {turn.thinking.map((text, index) => (
            <pre key={index} className="text">
              {text}
            </pre>
          ))}
        </details>
      ) : null}
      {turn.hidden_thinking > 0 ? (
        <p className="aside">{counted(turn.hidden_thinking, "blocco di ragionamento cifrato", "blocchi di ragionamento cifrati")}</p>
      ) : null}
      {turn.text.map((text, index) => (
        <p key={index} className="said-model">
          {text}
        </p>
      ))}
      {turn.tools.map((tool, index) => (
        <Tool key={index} tool={tool} report={report} />
      ))}
      {turn.notes.map((note, index) => (
        <div key={index} className="note">
          <span className="aside">L&apos;harness:</span> <Said text={note} />
        </div>
      ))}
    </li>
  );
}

function Tool({ tool, report }: { readonly tool: ReplayTool; readonly report: ReplayReport }) {
  return (
    <div className={`tool${tool.refused ? " refused" : ""}`}>
      <p>
        <code>{tool.name}</code>
        {tool.refused ? <strong className="back"> ha detto no</strong> : null}
        {!tool.answered ? <span className="aside"> nessuna risposta: il lavoro si è fermato prima</span> : null}
      </p>
      <details>
        <summary>Richiesta</summary>
        <pre className="text">{tool.input}</pre>
      </details>
      {tool.answered && tool.result !== "" ? <Said text={tool.result} /> : null}
      {/* A plain <img>, not next/image: the registry's images are not optimized (ADR-0024). */}
      {tool.images.map((image) =>
        image.servable ? (
          <img
            key={image.index}
            src={browserPaths.image(report.project, report.instance, image.index)}
            alt={`Immagine ${image.index + 1} restituita da ${tool.name}`}
            loading="lazy"
            className="seen"
          />
        ) : (
          <p key={image.index} className="aside">
            Immagine {image.media_type} non mostrata: il cruscotto serve solo PNG, JPEG, GIF e WebP.
          </p>
        ),
      )}
    </div>
  );
}
