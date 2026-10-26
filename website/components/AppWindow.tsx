"use client";
import { useEffect, useState } from "react";

const rows = [
  ["Existing", "/Images/layers.png", "451 KB"],
  ["Existing", "/Docs/report.docx", "88 KB"],
  ["Traced", "/Docs/case-notes.txt", "12 KB"],
  ["Existing", "/$MFT", "262 KB"],
  ["Traced", "/Photos/IMG_2041.jpg", "3.1 MB"],
];
const tabs = ["Overview", "Evidence", "Recovery", "Sanitization", "Reports", "Audit"];

export default function AppWindow() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((v) => (v >= rows.length + 3 ? 0 : v + 1)), 900);
    return () => clearInterval(t);
  }, []);
  const picked = n > rows.length;

  return (
    <div aria-label="Crypty app preview" className="overflow-hidden rounded-xl border border-line bg-panel shadow-2xl shadow-black/50">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5 font-semibold">
        <span className="grid size-6 place-items-center rounded-md bg-sage text-sm font-bold text-bg">C</span> Crypty
        <span className="ml-auto rounded-full border border-sage px-3 text-xs font-normal text-sage">Read-Only Mode</span>
      </div>
      <div className="flex gap-4 overflow-hidden border-b border-line px-4 py-2 text-xs text-dim">
        {tabs.map((t) => <span key={t} className={t === "Recovery" ? "border-b-2 border-sage text-sage" : ""}>{t}</span>)}
      </div>
      <div className="grid min-h-64 sm:grid-cols-[1.6fr_1fr]">
        <table className="w-full text-left text-xs">
          <thead className="text-dim"><tr><th className="p-2 font-medium">Status</th><th className="p-2 font-medium">Name</th><th className="p-2 font-medium">Size</th></tr></thead>
          <tbody>
            {n === 0 && <tr><td colSpan={3} className="p-3 text-dim">Scanning evidence…</td></tr>}
            {rows.slice(0, n).map(([s, name, size], i) => (
              <tr key={name} className={`border-t border-line ${picked && i === 2 ? "bg-sage/20" : ""}`}>
                <td className="p-2"><span className={`rounded px-2 py-0.5 ${s === "Traced" ? "bg-warn text-black" : "bg-line"}`}>{s}</span></td>
                <td className="whitespace-nowrap p-2">{name}</td><td className="whitespace-nowrap p-2">{size}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="space-y-1.5 border-t border-line p-3 text-xs sm:border-l sm:border-t-0">
          <b>File inspector</b>
          {picked ? (
            <>
              <p>case-notes.txt</p><p className="text-dim">Method: NTFS MFT trace</p><p className="text-dim">Confidence: 100%</p>
              <button className="mt-2 rounded bg-sage px-3 py-1 font-semibold text-bg">Recover Selected</button>
            </>
          ) : <p className="text-dim">Select an item</p>}
        </div>
      </div>
    </div>
  );
}
