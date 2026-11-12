import type { Metadata } from "next";

import type { FlowReport, Outcome, PhaseFlow, Setback, TicketFlow } from "../../../../api";
import { ApiError, api } from "../../../../api/client";
import { readForPage } from "../../../../api/read";
import { ProjectHeader } from "../../../../components/project-header";
import { SetbackList } from "../../../../components/setbacks";
import { Unavailable } from "../../../../components/unavailable";
import { count, usd, when } from "../../../../format";
import { pending, status, step } from "../../../../labels";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/projects/[name]/phases">): Promise<Metadata> {
  const { name } = await params;
  return { title: `${name}: fasi` };
}

/** The phases view: from the ideas to the delivery, where the work stopped and where it went back. */
export default async function Phases({ params }: PageProps<"/projects/[name]/phases">) {
  const { name } = await params;
  const report = await readForPage(() => api.flow(name));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  return (
    <>
      <ProjectHeader project={report.project} view="phases" />
      <Where outcome={report.outcome} tickets={report.tickets} />
      <Steps phases={report.phases} />
      <Setbacks setbacks={report.setbacks} />
      <Tickets report={report} />
    </>
  );
}

function Where({ outcome, tickets }: { readonly outcome: Outcome; readonly tickets: readonly TicketFlow[] }) {
  const byId = new Map(tickets.map((ticket) => [ticket.id, ticket]));
  return (
    <section aria-labelledby="where" className="outcome">
      <h2 id="where">Dove si è fermato</h2>
      <dl>
        <div>
          <dt>Consegna al cliente</dt>
          <dd>
            {outcome.delivery_id === null || outcome.delivery_status === null
              ? "nessun ticket di consegna"
              : `${outcome.delivery_id}, ${status(outcome.delivery_status)}`}
          </dd>
        </div>
        <div>
          <dt>Da finire</dt>
          <dd>
            {outcome.unfinished.length === 0 ? (
              "niente"
            ) : (
              <ul>
                {outcome.unfinished.map((id) => {
                  const ticket = byId.get(id);
                  return (
                    <li key={id}>
                      {id}
                      {ticket ? `, ${ticket.title}: ${pending(ticket.status)} (${ticket.assignee})` : ""}
                    </li>
                  );
                })}
              </ul>
            )}
          </dd>
        </div>
        <div>
          <dt>Ultimo passo</dt>
          <dd>
            {outcome.last_action === null || outcome.last_ticket_id === null
              ? "nessuno"
              : `${outcome.last_ticket_id} ${step(outcome.last_action)}, ${when(outcome.last_at)}`}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function Steps({ phases }: { readonly phases: readonly PhaseFlow[] }) {
  return (
    <section aria-labelledby="steps">
      <h2 id="steps">Dalle idee alla consegna</h2>
      <p className="aside">
        Le fasi in ordine di lavoro. Rifatto: ciò che un ticket è costato dopo il primo rimando del direttore.
        Senza esito: il costo dei ticket bloccati.
      </p>
      <div className="scroll" role="region" aria-label="Tabella delle fasi, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Fasi">
          <thead>
            <tr>
              <th scope="col">Fase</th>
              <th scope="col">Inizio</th>
              <th scope="col" className="number">Chiamate</th>
              <th scope="col" className="number">Costo</th>
              <th scope="col" className="number">Ticket</th>
              <th scope="col" className="number">Consegne</th>
              <th scope="col" className="number">Rimandi</th>
              <th scope="col" className="number">Bloccati</th>
              <th scope="col" className="number">Rifatto</th>
              <th scope="col" className="number">Senza esito</th>
            </tr>
          </thead>
          <tbody>
            {phases.map((item) => (
              <tr key={item.phase}>
                <th scope="row">{item.phase}</th>
                <td>{item.started_at === null ? "nessuna chiamata" : when(item.started_at)}</td>
                <td className="number">{count(item.calls)}</td>
                <td className="number">{usd(item.cost_usd)}</td>
                <td className="number">{count(item.tickets)}</td>
                <td className="number">{count(item.deliveries)}</td>
                <td className={`number${item.reworks > 0 ? " back" : ""}`}>{count(item.reworks)}</td>
                <td className={`number${item.blocked > 0 ? " back" : ""}`}>{count(item.blocked)}</td>
                <td className={`number${item.redone_usd > 0 ? " back" : ""}`}>{usd(item.redone_usd)}</td>
                <td className={`number${item.blocked_usd > 0 ? " back" : ""}`}>{usd(item.blocked_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Setbacks({ setbacks }: { readonly setbacks: readonly Setback[] }) {
  return (
    <section aria-labelledby="setbacks">
      <h2 id="setbacks">Passi indietro</h2>
      <SetbackList setbacks={setbacks} />
    </section>
  );
}

function Tickets({ report }: { readonly report: FlowReport }) {
  return (
    <section aria-labelledby="tickets">
      <h2 id="tickets">Ticket, passo per passo</h2>
      <div className="scroll" role="region" aria-label="Tabella dei ticket, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Storia dei ticket">
          <thead>
            <tr>
              <th scope="col">Ticket</th>
              <th scope="col">Fase</th>
              <th scope="col">Passi</th>
              <th scope="col" className="number">Costo</th>
              <th scope="col" className="number">Rifatto</th>
            </tr>
          </thead>
          <tbody>
            {report.tickets.map((ticket) => (
              <tr key={ticket.id}>
                <th scope="row">
                  {ticket.id}
                  <span className="aside"> {ticket.title}</span>
                </th>
                <td>{ticket.phase}</td>
                <td>
                  <ol className="path" aria-label={`Passi di ${ticket.id}`}>
                    {ticket.steps.map((item, index) => (
                      <li key={`${item.at}-${index}`} className={item.setback ? "back" : undefined}>
                        {step(item.action)}
                      </li>
                    ))}
                  </ol>
                  {ticket.verdict !== null ? <span className="aside"> verdetto {ticket.verdict}</span> : null}
                </td>
                <td className="number">{usd(ticket.cost_usd)}</td>
                <td className="number">{usd(ticket.redone_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
