import { authFetch } from "@/lib/auth-api";

export async function POST(req: Request) {
  const { username, password } = await req.json().catch(() => ({}));
  return authFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}
