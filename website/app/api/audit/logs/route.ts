import { authFetch, bearer } from "@/lib/auth-api";

export const GET = (req: Request) =>
  authFetch("/api/audit/logs", { headers: bearer(req) });
