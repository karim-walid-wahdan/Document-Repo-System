import api from "./client";

// in-memory caches so we don't refetch on every visit
let deptCache = null;             // [{department_id, name, location}]
const rolesCache = new Map();     // depId -> [{role_id, name}]

export async function getDepartments() {
  if (deptCache) return deptCache;
  const { data } = await api.get("/departments", { params: { limit: 1000 } });
  deptCache = data;
  return deptCache;
}

export async function getRolesByDepartment(departmentId) {
  if (rolesCache.has(departmentId)) return rolesCache.get(departmentId);
  const { data } = await api.get(`/departments/${departmentId}/roles`);
  rolesCache.set(departmentId, data);
  return data;
}
