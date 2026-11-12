import type { Metadata } from "next";

import type { QualityReport } from "../../../../api";
import { ApiError, api } from "../../../../api/client";
import { readForPage } from "../../../../api/read";
import { ProjectHeader } from "../../../../components/project-header";
import { Said } from "../../../../components/said";
import { SetbackList } from "../../../../components/setbacks";
import { Unavailable } from "../../../../components/unavailable";
import { count, counted, share, when } from "../../../../format";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/projects/[name]/quality">): Promise<Metadata> {
  const { name } = await params;
  return { title: `${name}: strumenti e QA` };
}

/** The tools and QA view: where the work goes wrong, in the words of whoever said no. */
export default async function Quality({ params }: PageProps<"/projects/[name]/quality">) {
  const { name } = await params;
  const report = await readForPage(() => api.quality(name));
  if (report instanceof ApiError) return <Unavailable error={report} />;
  return (
    <>
      <ProjectHeader project={report.project} view="quality" />
      <Brief report={report} />
      <section aria-labelledby="setbacks">
        <h2 id="setbacks">Passi indietro, con il motivo</h2>
        <SetbackList setbacks={report.setbacks} />
      </section>
      <Checks report={report} />
      <Tools report={report} />
    </>
  );
}

function Brief({ report }: { readonly report: QualityReport }) {
  return (
    <dl className="summary" aria-label="In breve">
      <div>
        <dt>Controlli al primo colpo</dt>
        <dd>
          {report.subjects > 0 ? share(report.first_pass / report.subjects) : "–"}
          <span className="aside">
            {" "}
            {count(report.first_pass)} di {counted(report.subjects, "file controllato", "file controllati")}
          </span>
        </dd>
      </div>
      <div>
        <dt>Strumenti che dicono no</dt>
        <dd>
          {count(report.refused)}
          <span className="aside"> su {counted(report.uses, "uso", "usi")}</span>
        </dd>
      </div>
      <div>
        <dt>Ticket bloccati</dt>
        <dd>
          {count(report.blocked)}
          <span className="aside"> e {counted(report.setbacks.length, "passo indietro", "passi indietro")} in tutto</span>
        </dd>
      </div>
    </dl>
  );
}

function Checks({ report }: { readonly report: QualityReport }) {
  return (
    <section aria-labelledby="checks">
      <h2 id="checks">Controlli</h2>
      <p className="aside">
        Un controllo passa al primo colpo su un file quando la sua prima prova su quel file non è FAIL. PASS,
        NOT_APPLICABLE e MEASURED non bocciano.
      </p>
      <div className="scroll" role="region" aria-label="Tabella dei controlli, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Controlli">
          <thead>
            <tr>
              <th scope="col">Controllo</th>
              <th scope="col" className="number">Prove</th>
              <th scope="col" className="number">FAIL</th>
              <th scope="col" className="number">Al primo colpo</th>
            </tr>
          </thead>
          <tbody>
            {report.checks.map((item) => (
              <tr key={item.check_name}>
                <th scope="row">
                  <code>{item.check_name}</code>
                </th>
                <td className="number">{count(item.runs)}</td>
                <td className={`number${item.failed > 0 ? " back" : ""}`}>{count(item.failed)}</td>
                <td className="number">
                  {count(item.first_pass)} di {count(item.subjects)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Prove fallite, per controllo</h3>
      {report.failures.length === 0 ? (
        <p>Nessuna prova FAIL.</p>
      ) : (
        report.checks
          .filter((check) => check.failed > 0)
          .map((check) => (
            <details key={check.check_name} className="group">
              <summary>
                <code>{check.check_name}</code>: {counted(check.failed, "prova FAIL", "prove FAIL")}
              </summary>
              <ol className="noes" aria-label={`Prove fallite di ${check.check_name}`}>
                {report.failures
                  .filter((item) => item.check_name === check.check_name)
                  .map((item, index) => (
                    <li key={`${item.at}-${index}`}>
                      <span className="when">{when(item.at)}</span>
                      <div>
                        su {item.file}, {item.ticket_id} {item.title}
                        <span className="aside"> firmata da {item.signer}</span>
                        <Said text={item.reason} />
                      </div>
                      <span className="aside">{item.phase}</span>
                    </li>
                  ))}
              </ol>
            </details>
          ))
      )}
    </section>
  );
}

function Tools({ report }: { readonly report: QualityReport }) {
  return (
    <section aria-labelledby="tools">
      <h2 id="tools">Strumenti</h2>
      <p className="aside">
        Dalle trascrizioni delle istanze: ogni richiesta del modello a uno strumento, e quando lo strumento ha detto
        no, il suo testo.
      </p>
      <div className="scroll" role="region" aria-label="Tabella degli strumenti, scorre in orizzontale" tabIndex={0}>
        <table aria-label="Strumenti">
          <thead>
            <tr>
              <th scope="col">Strumento</th>
              <th scope="col" className="number">Usi</th>
              <th scope="col" className="number">Rifiuti</th>
              <th scope="col" className="number">Istanze</th>
            </tr>
          </thead>
          <tbody>
            {report.tools.map((item) => (
              <tr key={item.tool}>
                <th scope="row">
                  <code>{item.tool}</code>
                </th>
                <td className="number">{count(item.uses)}</td>
                <td className={`number${item.refused > 0 ? " back" : ""}`}>{count(item.refused)}</td>
                <td className="number">{count(item.instances)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Rifiuti, per strumento</h3>
      {report.refusals.length === 0 ? (
        <p>Nessuno strumento ha detto no.</p>
      ) : (
        report.tools
          .filter((tool) => tool.refused > 0)
          .map((tool) => (
            <details key={tool.tool} className="group">
              <summary>
                <code>{tool.tool}</code> ha detto no {counted(tool.refused, "volta", "volte")} su{" "}
                {counted(tool.uses, "uso", "usi")}
              </summary>
              <ol className="noes" aria-label={`Rifiuti di ${tool.tool}`}>
                {report.refusals
                  .filter((item) => item.tool === tool.tool)
                  .map((item, index) => (
                    <li key={`${item.instance}-${item.turn}-${index}`}>
                      <span className="when">
                        {item.instance}, turno {item.turn}
                      </span>
                      <div>
                        {item.role !== "" ? <span className="aside">a {item.role}</span> : null}
                        <Said text={item.message} />
                      </div>
                      <span className="aside">{item.phase}</span>
                    </li>
                  ))}
              </ol>
            </details>
          ))
      )}
    </section>
  );
}
