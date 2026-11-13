import Link from "next/link";

/** A project's views, in the order they are read. */
const VIEWS = [
  { id: "run", label: "Run", path: "" },
  { id: "phases", label: "Fasi", path: "/phases" },
  { id: "model", label: "Modello", path: "/model" },
  { id: "quality", label: "Strumenti e QA", path: "/quality" },
  { id: "replay", label: "Replay", path: "/replay" },
] as const;

export type View = (typeof VIEWS)[number]["id"];

/** The project's name and its views; the open one says so to screen readers too. */
export function ProjectHeader({ project, view }: { readonly project: string; readonly view: View }) {
  const base = `/projects/${encodeURIComponent(project)}`;
  return (
    <header className="project">
      <h1>{project}</h1>
      <nav aria-label="Viste del progetto">
        <ul>
          {VIEWS.map((item) => (
            <li key={item.id}>
              <Link href={`${base}${item.path}`} aria-current={item.id === view ? "page" : undefined}>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
