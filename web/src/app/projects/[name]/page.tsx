import type { Metadata } from "next";

import type { ProjectReport } from "../../../api";
import { ApiError, api } from "../../../api/client";
import { readForPage } from "../../../api/read";
import { ProjectHeader } from "../../../components/project-header";
import { ScrollRegion } from "../../../components/scroll-region";
import { Timeline } from "../../../components/timeline";
import { Unavailable } from "../../../components/unavailable";
import { count, counted, minutes, seconds, share, usd, when } from "../../../lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/projects/[name]">): Promise<Metadata> {
  const { name } = await params;
  return { title: `${name}: run` };
}

/** The run view: what it cost and how long it took, and who worked when. */
export default async function Run({ params }: PageProps<"/projects/[name]">) {
  const { name } = await params;
  const report = await readForPage(() => api.report(name));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  const { started_at: start, ended_at: end } = report;
  return (
    <>
      <ProjectHeader project={report.project} view="run" />
      <Summary report={report} />
      <section aria-labelledby="timeline">
        <h2 id="timeline">Istanze nel tempo</h2>
        {start !== null && end !== null ? (
          <Timeline instances={report.instances} waits={report.waits} start={start} end={end} />
        ) : (
          <p>Nessuna chiamata registrata.</p>
        )}
      </section>
      <Phases report={report} />
      <Roles report={report} />
      <Tickets report={report} />
    </>
  );
}

function Summary({ report }: { readonly report: ProjectReport }) {
  const budget = report.budget_usd;
  return (
    <dl className="summary" aria-label="Riepilogo">
      <div>
        <dt>Costo</dt>
        <dd>
          {usd(report.cost_usd)}
          {budget !== null && budget > 0 ? (
            <span className="aside">
              {" "}
              su {usd(budget)} ({share(report.cost_usd / budget)})
            </span>
          ) : null}
        </dd>
        {budget !== null && budget > 0 ? (
          <meter min={0} max={budget} value={Math.min(report.cost_usd, budget)} aria-label="Budget usato" />
        ) : null}
      </div>
      <div>
        <dt>Durata</dt>
        <dd>
          {minutes(report.working_minutes)}
          <span className="aside">
            {" "}
            di lavoro
            {report.waits.length > 0
              ? `, più ${minutes(report.elapsed_minutes - report.working_minutes)} in attesa del cliente`
              : ""}
            , dal {when(report.started_at)} al {when(report.ended_at)}
          </span>
        </dd>
      </div>
      <div>
        <dt>Chiamate</dt>
        <dd>
          {count(report.calls)}
          <span className="aside">
            {" "}
            in {counted(report.instances.length, "istanza", "istanze")}, fino a {report.parallel} insieme
          </span>
        </dd>
      </div>
      <div>
        <dt>Cache</dt>
        <dd>
          {share(report.cache_hit)}
          <span className="aside"> dei token in ingresso, contesto medio {count(report.mean_context)}</span>
        </dd>
      </div>
      {report.to_presentation !== null ? (
        <div>
          <dt>Fino alla presentazione</dt>
          <dd>
            {usd(report.to_presentation.cost_usd)}
            <span className="aside">
              {" "}
              in {counted(report.to_presentation.calls, "chiamata", "chiamate")} e {minutes(report.to_presentation.minutes)}
            </span>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function Phases({ report }: { readonly report: ProjectReport }) {
  const measured = report.phases.reduce((total, phase) => total + phase.measured, 0);
  return (
    <section aria-labelledby="phases">
      <h2 id="phases">Per fase</h2>
      <p className="aside">
        Durata e TTFT sono misurati su {count(measured)} di {counted(report.calls, "chiamata", "chiamate")}.
      </p>
      <ScrollRegion label="Tabella delle fasi, scorre in orizzontale">
        <table aria-label="Fasi">
          <thead>
            <tr>
              <th scope="col">Fase</th>
              <th scope="col" className="number">Chiamate</th>
              <th scope="col" className="number">Costo</th>
              <th scope="col" className="number">Durata media</th>
              <th scope="col" className="number">TTFT mediano</th>
              <th scope="col" className="number">Ragionamento</th>
            </tr>
          </thead>
          <tbody>
            {report.phases.map((phase) => (
              <tr key={phase.phase}>
                <th scope="row">{phase.phase}</th>
                <td className="number">{count(phase.calls)}</td>
                <td className="number">{usd(phase.cost_usd)}</td>
                <td className="number">{seconds(phase.mean_duration_ms)}</td>
                <td className="number">{seconds(phase.median_ttft_ms)}</td>
                <td className="number">{count(phase.reasoning_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

function Roles({ report }: { readonly report: ProjectReport }) {
  return (
    <section aria-labelledby="roles">
      <h2 id="roles">Per ruolo</h2>
      <ScrollRegion label="Tabella dei ruoli, scorre in orizzontale">
        <table aria-label="Ruoli">
          <thead>
            <tr>
              <th scope="col">Ruolo</th>
              <th scope="col" className="number">Chiamate</th>
              <th scope="col" className="number">Costo</th>
              <th scope="col" className="number">Contesto medio</th>
              <th scope="col" className="number">Output</th>
            </tr>
          </thead>
          <tbody>
            {report.roles.map((role) => (
              <tr key={role.role}>
                <th scope="row">{role.role}</th>
                <td className="number">{count(role.calls)}</td>
                <td className="number">{usd(role.cost_usd)}</td>
                <td className="number">{count(role.mean_context)}</td>
                <td className="number">{count(role.output_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

function Tickets({ report }: { readonly report: ProjectReport }) {
  return (
    <section aria-labelledby="tickets">
      <h2 id="tickets">Ticket</h2>
      <ScrollRegion label="Tabella dei ticket, scorre in orizzontale">
        <table aria-label="Ticket">
          <thead>
            <tr>
              <th scope="col">Ticket</th>
              <th scope="col">Stato</th>
              <th scope="col">Assegnato a</th>
              <th scope="col">Titolo</th>
              <th scope="col" className="number">Costo</th>
            </tr>
          </thead>
          <tbody>
            {report.tickets.map((ticket) => (
              <tr key={ticket.id}>
                <th scope="row">{ticket.id}</th>
                <td>
                  {ticket.status}
                  {ticket.verdict !== null ? ` · ${ticket.verdict}` : ""}
                </td>
                <td>{ticket.assignee}</td>
                <td>{ticket.title}</td>
                <td className="number">{usd(ticket.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}
