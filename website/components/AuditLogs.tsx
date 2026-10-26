"use client";

import { useState } from "react";

type AuditLog = {
  id: number;
  timestamp: string;
  account: string | null;
  account_plan: string | null;
  case_id: string | null;
  case_name: string | null;
  device_fingerprint: string | null;
  action: string;
  details: string | null;
};

type Integrity = { valid: boolean; message: string };

const input = "mt-1 w-full rounded-md border border-line bg-bg p-2.5 text-ink outline-sage focus-visible:outline-2";

export default function AuditLogs() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function authorizedFetch<T>(path: string): Promise<T> {
    const response = await fetch(path, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? "The audit service rejected the request.");
    return result as T;
  }

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/account/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Sign-in failed.");
      setToken(result.token);
      const headers = { Authorization: `Bearer ${result.token}` };
      const [auditResponse, verifyResponse] = await Promise.all([
        fetch("/api/audit/logs", { headers, cache: "no-store" }),
        fetch("/api/audit/verify", { headers, cache: "no-store" }),
      ]);
      const [auditBody, verifyBody] = await Promise.all([auditResponse.json(), verifyResponse.json()]);
      if (!auditResponse.ok) throw new Error(auditBody.error ?? "Audit log access was denied. An admin or auditor account is required.");
      if (!verifyResponse.ok) throw new Error(verifyBody.error ?? "Could not verify the audit log.");
      setLogs(auditBody as AuditLog[]);
      setIntegrity(verifyBody as Integrity);
      setPassword("");
    } catch (reason) {
      setToken("");
      setLogs([]);
      setIntegrity(null);
      setError(reason instanceof Error ? reason.message : "Could not load audit logs.");
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const [entries, verification] = await Promise.all([
        authorizedFetch<AuditLog[]>("/api/audit/logs"),
        authorizedFetch<Integrity>("/api/audit/verify"),
      ]);
      setLogs(entries);
      setIntegrity(verification);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not refresh audit logs.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-5 py-10">
      <a className="text-sm text-sage hover:underline" href="/">← Crypty home</a>
      <h1 className="mb-2 mt-5 text-3xl font-bold">Audit logs</h1>
      <p className="mb-6 text-dim">Account, plan, case, device fingerprint, and action history from the Crypty account database.</p>

      {!token && (
        <form onSubmit={signIn} className="mb-6 max-w-md rounded-xl border border-line bg-panel p-5">
          <h2 className="mb-1 text-lg font-semibold">Authorized access</h2>
          <p className="mb-3 text-sm text-dim">Sign in with an admin or auditor account to view the audit trail.</p>
          <label htmlFor="audit-username" className="text-sm text-dim">Username</label>
          <input id="audit-username" className={input} autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} />
          <label htmlFor="audit-password" className="mt-3 block text-sm text-dim">Password</label>
          <input id="audit-password" className={input} type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          <button className="mt-4 w-full rounded-md bg-sage px-5 py-3 font-semibold text-bg disabled:opacity-50" disabled={busy}>
            {busy ? "Loading…" : "Sign in and view logs"}
          </button>
        </form>
      )}

      {token && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-line bg-panel p-4">
          <div>
            <b>{integrity?.valid ? "Audit chain intact" : "Audit chain integrity warning"}</b>
            <p className="text-sm text-dim">{integrity?.message ?? "Integrity has not been verified."}</p>
          </div>
          <button type="button" onClick={refresh} disabled={busy} className="rounded-md border border-line px-4 py-2 disabled:opacity-50">
            {busy ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      )}
      {error && <p role="alert" className="mb-4 rounded-md border border-bad/50 bg-panel p-3 text-bad">{error}</p>}

      {token && (
        <div className="overflow-x-auto rounded-xl border border-line bg-panel">
          <table className="w-full min-w-[1050px] text-left text-sm">
            <thead className="border-b border-line text-dim">
              <tr>
                {["Time", "Account", "Plan", "Case ID", "Case name", "Device fingerprint", "Action", "Details"].map((label) => (
                  <th key={label} className="px-3 py-3 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((entry) => (
                <tr key={entry.id} className="border-b border-line align-top last:border-0">
                  <td className="whitespace-nowrap px-3 py-3">{entry.timestamp}</td>
                  <td className="px-3 py-3">{entry.account ?? "—"}</td>
                  <td className="px-3 py-3">{entry.account_plan ?? "—"}</td>
                  <td className="max-w-40 break-all px-3 py-3">{entry.case_id ?? "—"}</td>
                  <td className="px-3 py-3">{entry.case_name ?? "—"}</td>
                  <td className="max-w-56 break-all font-mono text-xs px-3 py-3">{entry.device_fingerprint ?? "—"}</td>
                  <td className="whitespace-nowrap px-3 py-3 font-semibold">{entry.action}</td>
                  <td className="max-w-64 whitespace-pre-wrap px-3 py-3 text-dim">{entry.details ?? ""}</td>
                </tr>
              ))}
              {logs.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-dim">No audit entries recorded yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
