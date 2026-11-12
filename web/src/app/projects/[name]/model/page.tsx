import type { Metadata } from "next";

import type { BehaviourReport, InstanceTurns, StopCount } from "../../../../api";
import { ApiError, api } from "../../../../api/client";
import { readForPage } from "../../../../api/read";
import { InstanceTurnsView } from "../../../../components/context-chart";
import { ProjectHeader } from "../../../../components/project-header";
import { Unavailable } from "../../../../components/unavailable";
import { count, counted, seconds, share, usd } from "../../../../format";
import { stop } from "../../../../labels";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/projects/[name]/model">): Promise<Metadata> {
  const { name } = await params;
  return { title: `${name}: modello` };
}

/** The model view: how the model worked, role by role and turn by turn. */
export default async function Model({ params }: PageProps<"/projects/[name]/model">) {
  const { name } = await params;
  const report = await readForPage(() => api.behaviour(name));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  return (
    <>
      <ProjectHeader project={report.project} view="model" />
      <Stops stops={report.stop_reasons} />
      <Roles report={report} />
      <Turns instances={report.instances} />
    </>
  );
}

function Stops({ stops }: { readonly stops: readonly StopCount[] }) {
  const cut = stops.filter((item) => !item.complete).reduce((total, item) => total + item.calls, 0);
  return (
    <section aria-labelledby="stops">
      <h2 id="stops">Perché il modello si è fermato</h2>
      <ul className="stops" aria-label="Motivi di fine">
        {stops.map((item) => (
          <li key={item.reason} className={item.complete ? undefined : "cut"}>
            <strong>{count(item.calls)}</strong> <code>{item.reason}</code> <span className="aside">{stop(item.reason)}</span>
          </li>
        ))}
      </ul>
      <p className="aside">
        {cut === 0
          ? "Ogni risposta è arrivata intera."
          : `Risposte non arrivate intere: ${count(cut)}. Il ciclo dell'agente le scarta e le richiede, o blocca il ticket.`}
      </p>
    </section>
  );
}

function Roles({ report }: { readonly report: BehaviourReport }) {
  const measured = report.roles.reduce((total, role) => total + role.measured, 0);
  const calls = report.roles.reduce((total, role) => total + role.calls, 0);
  return (
    <section aria-labelledby="roles">
      <h2 id="roles">Per ruolo</h2>
      <p className="aside">
        Il contesto è ciò che il modello legge a ogni turno: ingresso, cache letta e cache scritta. Durata, TTFT,
        ragionamento ed effort sono misurati su {count(measured)} di {counted(calls, "chiamata", "chiamate")}.
      </p>
      <div className="scroll" role="region" aria-label="Tabella dei ruoli, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Ruoli">
          <thead>
            <tr>
              <th scope="col">Ruolo</th>
              <th scope="col" className="number">Chiamate</th>
              <th scope="col" className="number">Costo</th>
              <th scope="col" className="number">Contesto medio</th>
              <th scope="col" className="number">Contesto massimo</th>
              <th scope="col" className="number">Cache</th>
              <th scope="col" className="number">Ragionamento</th>
              <th scope="col" className="number">Durata media</th>
              <th scope="col" className="number">TTFT mediano</th>
              <th scope="col">Effort</th>
              <th scope="col">Fine</th>
            </tr>
          </thead>
          <tbody>
            {report.roles.map((role) => (
              <tr key={role.role}>
                <th scope="row">{role.role}</th>
                <td className="number">{count(role.calls)}</td>
                <td className="number">{usd(role.cost_usd)}</td>
                <td className="number">{count(role.mean_context)}</td>
                <td className="number">{count(role.max_context)}</td>
                <td className="number">{share(role.cache_hit)}</td>
                <td className="number">{count(role.reasoning_tokens)}</td>
                <td className="number">{seconds(role.mean_duration_ms)}</td>
                <td className="number">{seconds(role.median_ttft_ms)}</td>
                <td>{role.efforts.length > 0 ? role.efforts.join(", ") : "–"}</td>
                <td>{role.stop_reasons.map((item) => `${item.reason} ${count(item.calls)}`).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Turns({ instances }: { readonly instances: readonly InstanceTurns[] }) {
  // One scale for every instance, so the heights compare.
  const max = Math.max(0, ...instances.map((item) => item.peak_context));
  return (
    <section aria-labelledby="turns">
      <h2 id="turns">Contesto turno per turno</h2>
      <p className="aside">
        Una istanza per riquadro, in ordine di inizio. Stessa scala per tutte, da 0 a {count(max)} token.
      </p>
      <ol className="multiples" aria-label="Istanze">
        {instances.map((item) => (
          <li key={item.instance}>
            <h3>
              <strong>{item.phase}</strong> {item.instance}
            </h3>
            <p className="aside">
              {counted(item.turns.length, "turno", "turni")}, picco {count(item.peak_context)} token, cache{" "}
              {share(item.cache_hit)}
            </p>
            <InstanceTurnsView
              turns={item.turns}
              max={max}
              instance={item.instance}
              label={`Contesto per turno di ${item.instance}: ${counted(item.turns.length, "turno", "turni")}, picco ${count(item.peak_context)} token`}
            />
          </li>
        ))}
      </ol>
    </section>
  );
}
