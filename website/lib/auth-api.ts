import { NextResponse } from "next/server";
import type { Plan } from "./data";

const BASE = process.env.AUTH_API_URL ?? "http://127.0.0.1:5000";

/** Server-side call to the auth API. The browser never talks to it directly. */
export async function authFetch(path: string, init: RequestInit = {}, service = false) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (service) headers.set("X-Service-Key", process.env.CRYPTY_SERVICE_KEY ?? "");
  try {
    const r = await fetch(BASE + path, { ...init, headers, cache: "no-store" });
    const body = await r.json().catch(() => ({ error: "Unexpected response from the account service." }));
    return NextResponse.json(body, { status: r.status });
  } catch {
    return NextResponse.json({ error: "The account service is not reachable. Try again shortly." }, { status: 502 });
  }
}

export async function getPlans(): Promise<Plan[]> {
  try {
    const r = await fetch(BASE + "/api/plans", { cache: "no-store" });
    return r.ok ? await r.json() : [];
  } catch {
    return [];
  }
}

export const bearer = (req: Request) => ({ Authorization: req.headers.get("authorization") ?? "" });
