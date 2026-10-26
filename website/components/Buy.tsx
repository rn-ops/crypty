"use client";

import { useState } from "react";
import type { Plan } from "@/lib/data";

const card = "rounded-xl border border-line bg-panel p-5";
const input = "my-1.5 w-full rounded-md border border-line bg-bg p-2.5 text-ink outline-sage focus-visible:outline-2";
const button = "w-full rounded-md bg-sage px-5 py-3 font-semibold text-bg disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage";

type Signup = {
  message: string;
  account: { username: string; plan_name: string };
};

export default function Buy({ plans }: { plans: Plan[] }) {
  const [planId, setPlanId] = useState(plans[0]?.id ?? "");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedPlan = plans.find((plan) => plan.id === planId);

  const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
  };

  async function createAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const response = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, plan_id: planId }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Could not create the account.");
      const signup = result as Signup;
      setMessage(`${signup.message} Account: ${signup.account.username} · Plan: ${signup.account.plan_name}.`);
      setForm((current) => ({ ...current, password: "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section id="pricing" className="grid gap-8 py-12 lg:grid-cols-[1.1fr_.9fr]">
      <div>
        <h2 className="text-3xl font-bold">Choose a plan</h2>
        <p className="mb-5 mt-2 text-dim">Select the workspace plan for your Crypty account.</p>
        <div className="grid gap-4">
          {plans.map((plan) => (
            <button
              key={plan.id}
              type="button"
              aria-pressed={planId === plan.id}
              onClick={() => setPlanId(plan.id)}
              className={`${card} text-left ${planId === plan.id ? "border-sage ring-4 ring-sage/20" : ""}`}
            >
              <b className="text-lg">{plan.name}</b>
              <ul className="mt-2 list-disc pl-5 text-dim">
                {plan.features.map((feature) => <li key={feature}>{feature.replaceAll("_", " ")}</li>)}
              </ul>
            </button>
          ))}
          {plans.length === 0 && <p className="text-warn">Plans could not be loaded. Start the auth API and refresh.</p>}
        </div>
      </div>

      <form id="account" onSubmit={createAccount} className={card}>
        <h2 className="mb-1 text-2xl font-bold">Create your account</h2>
        <p className="mb-4 text-sm text-dim">Your account and selected plan will be saved in Crypty&apos;s account database.</p>
        <label className="text-sm text-dim" htmlFor="username">Username</label>
        <input id="username" className={input} autoComplete="username" minLength={3} maxLength={64} required value={form.username} onChange={update("username")} />
        <label className="text-sm text-dim" htmlFor="email">Email</label>
        <input id="email" className={input} type="email" autoComplete="email" required value={form.email} onChange={update("email")} />
        <label className="text-sm text-dim" htmlFor="password">Password (at least 10 characters)</label>
        <input id="password" className={input} type="password" autoComplete="new-password" minLength={10} required value={form.password} onChange={update("password")} />
        <p className="my-3 text-dim">Selected plan: <b className="text-ink">{selectedPlan?.name ?? "Select a plan"}</b></p>
        <button className={button} type="submit" disabled={!selectedPlan || busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        {error && <p role="alert" className="mt-3 text-bad">{error}</p>}
        {message && <p role="status" className="mt-3 text-sage">{message}</p>}
      </form>
    </section>
  );
}
