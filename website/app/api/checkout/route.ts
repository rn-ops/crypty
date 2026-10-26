import { authFetch } from "@/lib/auth-api";

// Create a Crypty account with the selected account plan.
export async function POST(req: Request) {
  const { username, email, password, plan_id } = await req.json().catch(() => ({}));
  return authFetch("/api/internal/signup", { method: "POST", body: JSON.stringify({ username, email, password, plan_id }) }, true);
}
