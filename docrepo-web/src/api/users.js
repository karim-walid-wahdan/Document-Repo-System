import api from "./client";
import { me as getMe } from "./auth";

// Try to resolve a text input to a user_id for /documents?uploader=<id>
// Strategy:
//  - "me" (case-insensitive) => current user's id
//  - numeric => treat as id
//  - email => if admin, try /users?q=email (admin-only), else best-effort fail (returns null)
export async function resolveUploaderId(input) {
  if (!input) return null;
  const s = String(input).trim();
  if (!s) return null;

  if (/^me$/i.test(s)) {
    const me = await getMe();
    return me?.user_id ?? null;
  }
  if (/^\d+$/.test(s)) return parseInt(s, 10);

  // if looks like email, try admin search
  if (s.includes("@")) {
    try {
      // Admin-only endpoint; will 403 for non-admins
      const { data } = await api.get("/users", { params: { q: s, limit: 1 } });
      if (Array.isArray(data) && data.length) return data[0].user_id;
    } catch {
      // ignore – non-admin or not found
    }
  }
  return null;
}
