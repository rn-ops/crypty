import AppWindow from "@/components/AppWindow";
import Buy from "@/components/Buy";
import { getPlans } from "@/lib/auth-api";

export const dynamic = "force-dynamic";

const features = [
  ["Recovery", "NTFS scanning with paths, timestamps and data runs. FAT32 and exFAT detectors."],
  ["Sanitization", "Procedures designed with reference to NIST SP 800-88 Rev. 2. Not certified."],
  ["Audit trail", "Role-based access and a log of every sign-in and operation."],
  ["Reports", "Per-case reports with sources, recovered files and hashes."],
];

export default async function Home() {
  const plans = await getPlans();
  return (
    <div className="mx-auto max-w-6xl bg-[radial-gradient(900px_500px_at_80%_-10%,#1f2d2b,transparent)] px-5">
      <header className="flex items-center justify-between py-4">
        <a href="#top" className="flex items-center gap-2.5 text-xl font-bold">
          <span className="grid size-7 place-items-center rounded-md bg-sage text-sm text-bg">C</span>Crypty
          <small className="hidden text-xs font-normal text-dim sm:inline">Digital forensics workspace</small>
        </a>
        <nav className="flex items-center gap-5 text-dim">
          <a href="#product" className="hidden sm:inline">Product</a>
          <a href="#pricing" className="hidden sm:inline">Plans</a>
          <a href="/audit" className="hidden sm:inline">Audit logs</a>
          <a href="#account" className="rounded-md bg-sage px-3.5 py-1.5 text-sm font-semibold text-bg">Create account</a>
        </nav>
      </header>

      <main id="top">
        <section className="grid items-center gap-9 pb-16 pt-10 lg:grid-cols-[.9fr_1.1fr]">
          <div>
            <span className="mb-4 inline-block rounded-full border border-line px-3 text-sm text-dim">Early access · Windows desktop</span>
            <h1 className="mb-4 text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">Recover what was deleted. Erase what must go.</h1>
            <p className="mb-6 text-lg text-dim">Crypty reads storage read-only, traces deleted NTFS files, and logs every action for your case report.</p>
            <a href="#pricing" className="inline-block rounded-md bg-sage px-6 py-3 font-semibold text-bg">Choose a plan</a>
          </div>
          <AppWindow />
        </section>

        <section id="product" className="grid gap-4 py-8 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(([t, d]) => (
            <div key={t} className="rounded-xl border border-line bg-panel p-5">
              <h3 className="mb-1.5 font-semibold">{t}</h3><p className="text-dim">{d}</p>
            </div>
          ))}
        </section>

        <Buy plans={plans} />
      </main>

      <footer className="border-t border-line py-6 text-sm text-dim">
        Crypty is an early-access prototype. Use recovery tools only on media you are authorised to examine.
      </footer>
    </div>
  );
}
