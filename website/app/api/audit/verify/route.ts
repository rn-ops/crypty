import { authFetch, bearer } from "@/lib/auth-api";

export const GET = (req: Request) =>
  authFetch("/api/audit/verify", { headers: bearer(req) });
