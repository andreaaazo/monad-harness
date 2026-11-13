import type { Metadata } from "next";

import type { BlindComparison, CompareReport, Execution, FingerprintDiff, ProjectSummary, Side } from "../../api";
import { ApiError, api } from "../../api/client";
import { readForPage } from "../../api/read";
import { Said } from "../../components/said";
import { ScrollRegion } from "../../components/scroll-region";
import { Unavailable } from "../../components/unavailable";
import { count, counted, minutes, share, signed, usd, when } from "../../lib/format";
import { fingerprintValue, status } from "../../lib/labels";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Confronto" };

const one = (value: string | string[] | undefined): string | undefined =>
  typeof value === "string" && value !== "" ? value : undefined;

/** The compare view: is it better than before? Two projects side by side, their fingerprints, the blind judgments. */
export default async function Compare({ searchParams }: PageProps<"/compare">) {
  const query = await searchParams;
  const projects = await readForPage(() => api.projects());
  if (projects instanceof ApiError) return <Unavailable error={projects} />;
  // Without a choice, the two projects that worked last: the earlier one and the later one.
  const recent = [...projects].sort((a, b) => (b.last_at ?? "").localeCompare(a.last_at ?? ""));
  const before = one(query.before) ?? recent[1]?.name;
  const after = one(query.after) ?? recent[0]?.name;
  return (
    <>
      <h1>Confronto</h1>
      <Choose projects={projects} before={before} after={after} />
      {before === undefined || after === undefined ? (
        <p>Per un confronto servono almeno due progetti nel registro.</p>
      ) : (
        <Result before={before} after={after} />
      )}
    </>
  );
}

function Choose({
  projects,
  before,
  after,
}: {
  readonly projects: readonly ProjectSummary[];
  readonly before: string | undefined;
  readonly after: string | undefined;
}) {
  return (
    <form method="get" action="/compare" className="choose" aria-label="Scegli i progetti">
      <label>
        Prima{" "}
        <select name="before" defaultValue={before}>
          {projects.map((project) => (
            <option key={project.name}>{project.name}</option>
          ))}
        </select>
      </label>
      <label>
        Dopo{" "}
        <select name="after" defaultValue={after}>
          {projects.map((project) => (
            <option key={project.name}>{project.name}</option>
          ))}
        </select>
      </label>
      <button type="submit">Confronta</button>
    </form>
  );
}

async function Result({ before, after }: { readonly before: string; readonly after: string }) {
  const report = await readForPage(() => api.compare(before, after));
  if (report instanceof ApiError && report.status === 400) {
    return (
      <p className="notice" role="alert">
        {report.detail}
      </p>
    );
  }
  if (report instanceof ApiError) return <Unavailable error={report} />;
  return (
    <>
      <Sides report={report} />
      <Phases report={report} />
      <Fingerprints report={report} />
      <Judgments report={report} />
    </>
  );
}

type Row = {
  readonly label: string;
  readonly before: string;
  readonly after: string;
  readonly delta?: string;
};

/** A measure both projects have: its two values, and how much it changed from the first to the second. */
function measured(label: string, before: number, after: number, format: (value: number) => string): Row {
  return { label, before: format(before), after: format(after), delta: signed(after - before, format) };
}

function rows(a: Side, b: Side): Row[] {
  const presentation = (side: Side) =>
    side.to_presentation === null
      ? "–"
      : `${usd(side.to_presentation.cost_usd)} in ${minutes(side.to_presentation.minutes)}`;
  const chosen = (value: string | null) => (value === null ? "non registrato" : value || "predefinito");
  const choice = (side: Side) => `${chosen(side.model)} · ${chosen(side.effort)}`;
  return [
    {
      label: "Consegna al cliente",
      before: a.delivery_status === null ? "–" : status(a.delivery_status),
      after: b.delivery_status === null ? "–" : status(b.delivery_status),
    },
    { label: "Modello · effort", before: choice(a), after: choice(b) },
    measured("Costo", a.cost_usd, b.cost_usd, usd),
    {
      label: "Budget",
      before: a.budget_usd === null ? "–" : usd(a.budget_usd),
      after: b.budget_usd === null ? "–" : usd(b.budget_usd),
    },
    measured("Chiamate", a.calls, b.calls, count),
    measured("Istanze", a.instances, b.instances, count),
    measured("Lavoro", a.working_minutes, b.working_minutes, minutes),
    measured("Attese del cliente", a.waiting_minutes, b.waiting_minutes, minutes),
    { label: "Fino alla presentazione", before: presentation(a), after: presentation(b) },
    { label: "Cache", before: share(a.cache_hit), after: share(b.cache_hit) },
    measured("Contesto medio", a.mean_context, b.mean_context, count),
    measured("Contesto massimo", a.peak_context, b.peak_context, count),
    measured("Rifatto", a.redone_usd, b.redone_usd, usd),
    measured("Senza esito", a.blocked_usd, b.blocked_usd, usd),
    {
      label: "Controlli al primo colpo",
      before: `${count(a.first_pass)} di ${count(a.subjects)}`,
      after: `${count(b.first_pass)} di ${count(b.subjects)}`,
    },
    {
      label: "Rifiuti degli strumenti",
      before: `${count(a.tool_refusals)} su ${counted(a.tool_uses, "uso", "usi")}`,
      after: `${count(b.tool_refusals)} su ${counted(b.tool_uses, "uso", "usi")}`,
    },
  ];
}

function Sides({ report }: { readonly report: CompareReport }) {
  const { before, after } = report;
  return (
    <section aria-labelledby="sides">
      <h2 id="sides">Affiancati</h2>
      <p className="aside">La differenza è sempre dopo meno prima.</p>
      <ScrollRegion label="Tabella dei due progetti, scorre in orizzontale">
        <table aria-label="Affiancati">
          <thead>
            <tr>
              <th scope="col">Misura</th>
              <th scope="col" className="number">
                {before.project}
              </th>
              <th scope="col" className="number">
                {after.project}
              </th>
              <th scope="col" className="number">
                Differenza
              </th>
            </tr>
          </thead>
          <tbody>
            {rows(before, after).map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td className="number">{row.before}</td>
                <td className="number">{row.after}</td>
                <td className="number">{row.delta ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

function Phases({ report }: { readonly report: CompareReport }) {
  const cost = (value: number | null) => (value === null ? "–" : usd(value));
  return (
    <section aria-labelledby="phases">
      <h2 id="phases">Per fase</h2>
      <p className="aside">
        Per nome di fase, in ordine di lavoro del progetto di dopo. Un trattino: la fase da quella parte non c&apos;è.
        Nei progetti di prima di M1.5 la fase porta il nome del ruolo.
      </p>
      <ScrollRegion label="Tabella delle fasi affiancate, scorre in orizzontale">
        <table aria-label="Fasi affiancate">
          <thead>
            <tr>
              <th scope="col">Fase</th>
              <th scope="col" className="number">
                {report.before.project}
              </th>
              <th scope="col" className="number">
                {report.after.project}
              </th>
              <th scope="col" className="number">
                Differenza
              </th>
            </tr>
          </thead>
          <tbody>
            {report.phases.map((item) => (
              <tr key={item.phase}>
                <th scope="row">{item.phase}</th>
                <td className="number">{cost(item.before_usd)}</td>
                <td className="number">{cost(item.after_usd)}</td>
                <td className="number">
                  {item.before_usd !== null && item.after_usd !== null ? signed(item.after_usd - item.before_usd, usd) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

const STATES: Readonly<Record<FingerprintDiff["state"], (before: string, after: string) => string>> = {
  entrambe: () => "",
  "manca prima": (before) => `${before} non ha un'impronta: ha lavorato prima che le esecuzioni la registrassero.`,
  "manca dopo": (_, after) => `${after} non ha un'impronta: ha lavorato prima che le esecuzioni la registrassero.`,
  nessuna: (before, after) =>
    `Né ${before} né ${after} hanno un'impronta: hanno lavorato prima che le esecuzioni la registrassero.`,
};

function Fingerprints({ report }: { readonly report: CompareReport }) {
  const { fingerprint, before, after } = report;
  return (
    <section aria-labelledby="fingerprint">
      <h2 id="fingerprint">Impronta</h2>
      {fingerprint.state !== "entrambe" ? (
        <p>{STATES[fingerprint.state](before.project, after.project)}</p>
      ) : (
        <>
          <p>
            Dall&apos;ultima esecuzione di {before.project} (#{fingerprint.before_run}) alla prima di {after.project} (#
            {fingerprint.after_run}):{" "}
            {fingerprint.changes.length === 0 ? "nessuna differenza." : `${counted(fingerprint.changes.length, "differenza", "differenze")}.`}
          </p>
          {fingerprint.changes.length > 0 ? (
            <ScrollRegion label="Differenze di impronta, scorrono in orizzontale">
              <table aria-label="Differenze di impronta">
                <thead>
                  <tr>
                    <th scope="col">Parte</th>
                    <th scope="col">Elemento</th>
                    <th scope="col">Prima</th>
                    <th scope="col">Dopo</th>
                  </tr>
                </thead>
                <tbody>
                  {fingerprint.changes.map((item) => (
                    <tr key={`${item.part}-${item.item}`}>
                      <th scope="row">{item.part}</th>
                      <td>
                        <code>{item.item}</code>
                      </td>
                      <td>
                        <code>{fingerprintValue(item.before)}</code>
                      </td>
                      <td>
                        <code>{fingerprintValue(item.after)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          ) : null}
        </>
      )}
      <div className="pair">
        <Executions side={before} />
        <Executions side={after} />
      </div>
    </section>
  );
}

function Executions({ side }: { readonly side: Side }) {
  const distance = (item: Execution) => {
    if (!item.readable) return "impronta di una forma che questa versione non legge";
    if (item.changes_from_previous === null) return "la prima";
    if (item.changes_from_previous === 0) return "identica alla precedente";
    return `${counted(item.changes_from_previous, "differenza", "differenze")} dalla precedente`;
  };
  return (
    <div>
      <h3>Esecuzioni di {side.project}</h3>
      {side.executions.length === 0 ? (
        <p className="aside">Nessuna esecuzione con impronta.</p>
      ) : (
        <ol className="executions" aria-label={`Esecuzioni di ${side.project}`}>
          {side.executions.map((item) => (
            <li key={item.seq}>
              <strong>
                #{item.seq} {item.command}
              </strong>{" "}
              <code>{item.digest.slice(0, 12)}</code>
              <span className="aside">
                {" "}
                {when(item.at)}, {counted(item.calls, "chiamata", "chiamate")}, {usd(item.cost_usd)}: {distance(item)}
              </span>
            </li>
          ))}
        </ol>
      )}
      {side.unrecorded_calls > 0 ? (
        <p className="aside">
          {counted(side.unrecorded_calls, "chiamata", "chiamate")} senza esecuzione: di prima delle impronte.
        </p>
      ) : null}
    </div>
  );
}

function Judgments({ report }: { readonly report: CompareReport }) {
  const { before, after } = report;
  return (
    <section aria-labelledby="judgments">
      <h2 id="judgments">Giudizi alla cieca</h2>
      {report.judgments.length === 0 ? (
        <p>
          Nessun giudizio alla cieca fra {before.project} e {after.project}. Si registra con{" "}
          <code>uv run agency judge &lt;file&gt; &lt;file&gt;</code>.
        </p>
      ) : (
        report.judgments.map((item) => <Judged key={item.comparison} judged={item} />)
      )}
    </section>
  );
}

function Judged({ judged }: { readonly judged: BlindComparison }) {
  return (
    <div className="judged">
      <h3>
        Confronto {judged.comparison}
        <span className="aside">
          {" "}
          di {judged.judge}, {when(judged.at)}
        </span>
      </h3>
      <ScrollRegion label={`Voti del confronto ${judged.comparison}`}>
        <table aria-label={`Voti del confronto ${judged.comparison}`}>
          <thead>
            <tr>
              <th scope="col">Lettera</th>
              <th scope="col">Da dove viene</th>
              <th scope="col">Livello</th>
              <th scope="col">Test di sostituzione</th>
              <th scope="col">Perché</th>
            </tr>
          </thead>
          <tbody>
            {judged.votes.map((vote) => (
              <tr key={vote.letter}>
                <th scope="row">
                  {vote.letter}
                  {vote.best ? <strong className="best"> il migliore</strong> : null}
                </th>
                <td>
                  {vote.project === "" ? "fuori dai progetti" : vote.project}
                  <span className="aside"> {vote.file}</span>
                </td>
                <td>{vote.level}</td>
                <td>{vote.specific ? "regge: specifico" : "non regge: generico"}</td>
                <td>
                  <Said text={vote.why} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </div>
  );
}
