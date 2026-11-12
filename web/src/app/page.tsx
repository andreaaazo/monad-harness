import Link from "next/link";

import { ApiError, api } from "../api/client";
import { readForPage } from "../api/read";
import { Unavailable } from "../components/unavailable";
import { count, counted, share, usd, when } from "../lib/format";

// Every request reads the data of that moment: no page is built with data during the build.
export const dynamic = "force-dynamic";

export default async function Projects() {
  const read = await readForPage(() => Promise.all([api.projects(), api.provenance()]));
  if (read instanceof ApiError) return <Unavailable error={read} />;
  const [projects, provenance] = read;
  const measured = provenance.calls === 0 ? 0 : (provenance.calls - provenance.unmeasured) / provenance.calls;
  return (
    <>
      <h1>Progetti</h1>
      <table aria-label="Progetti">
        <thead>
          <tr>
            <th scope="col">Progetto</th>
            <th scope="col" className="number">Costo</th>
            <th scope="col" className="number">Budget</th>
            <th scope="col" className="number">Chiamate</th>
            <th scope="col">Ultimo lavoro</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.name}>
              <th scope="row">
                <Link href={`/projects/${encodeURIComponent(project.name)}`}>{project.name}</Link>
              </th>
              <td className="number">{usd(project.cost_usd)}</td>
              <td className="number">{project.budget_usd === null ? "–" : usd(project.budget_usd)}</td>
              <td className="number">{count(project.calls)}</td>
              <td>{when(project.last_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="provenance" aria-label="Provenienza dei dati">
        Dati del registro alla revisione {provenance.registry_revision}, letti {when(provenance.built_at)}.{" "}
        Misure per {share(measured)} di {counted(provenance.calls, "chiamata", "chiamate")}: {count(provenance.from_registry)} dal
        registro, {count(provenance.from_traces)} dalle tracce.
      </p>
    </>
  );
}
