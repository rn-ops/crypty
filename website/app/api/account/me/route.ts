import { authFetch, bearer } from "@/lib/auth-api";

export const GET = (req: Request) => authFetch("/api/account/me", { headers: bearer(req) });
