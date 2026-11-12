import type { Metadata } from "next";
import Link from "next/link";

import { ApiError, api } from "../../../../api/client";
import { readForPage } from "../../../../api/read";
import { ProjectHeader } from "../../../../components/project-header";
import { Unavailable } from "../../../../components/unavailable";
import { count, usd, when } from "../../../../format";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/projects/[name]/replay">): Promise<Metadata> {
  const { name } = await params;
  return { title: `${name}: replay` };
}

/** A project's instances, in order of start: from here, one opens turn by turn. */
export default async function Instances({ params }: PageProps<"/projects/[name]/replay">) {
  const { name } = await params;
  const report = await readForPage(() => api.report(name));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  const base = `/projects/${encodeURIComponent(report.project)}/replay`;
  return (
    <>
      <ProjectHeader project={report.project} view="replay" />
      <p className="aside">Ogni istanza com&apos;è andata davvero: ciò che il modello ha pensato, scritto e chiesto, e ciò che gli è tornato.</p>
      <div className="scroll" role="region" aria-label="Tabella delle istanze, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Istanze">
          <thead>
            <tr>
              <th scope="col">Istanza</th>
              <th scope="col">Fase</th>
              <th scope="col">Ruolo</th>
              <th scope="col">Inizio</th>
              <th scope="col" className="number">Chiamate</th>
              <th scope="col" className="number">Costo</th>
            </tr>
          </thead>
          <tbody>
            {report.instances.map((item) => (
              <tr key={item.instance}>
                <th scope="row">
                  <Link href={`${base}/${encodeURIComponent(item.instance)}`}>{item.instance}</Link>
                </th>
                <td>{item.phase}</td>
                <td>{item.role}</td>
                <td>{when(item.started_at)}</td>
                <td className="number">{count(item.calls)}</td>
                <td className="number">{usd(item.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
