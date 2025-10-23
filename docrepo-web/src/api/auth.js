import api, { setTokens, clearTokens } from "./client";

export async function register(email, password, roleId = 2, deptId = 1) {
  const { data } = await api.post("/auth/register", {
    email, password, role_id: roleId, department_id: deptId,
  });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logout() {
  try { await api.post("/auth/logout"); } finally { clearTokens(); }
}

export async function me() {
  const { data } = await api.get("/users/me");
  return data;
}
