import Link from "next/link";

export default function NotFound() {
  return (
    <section className="notice">
      <h1>Progetto sconosciuto</h1>
      <p>Il registro non ha un progetto con questo nome.</p>
      <p>
        <Link href="/">Torna ai progetti</Link>
      </p>
    </section>
  );
}
