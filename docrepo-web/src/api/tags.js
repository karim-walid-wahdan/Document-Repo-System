import api from "./client";

let cache = new Map(); // prefix -> [{tag_id, name}]
let allCache = null;

export async function searchTags(prefix = "", limit = 20) {
  const key = `${prefix}|${limit}`;
  if (cache.has(key)) return cache.get(key);
  const { data } = await api.get("/tags", { params: prefix ? { q: prefix, limit } : { limit } });
  cache.set(key, data);
  return data;
}

export async function listAllTags(limit = 200) {
  if (allCache) return allCache;
  const { data } = await api.get("/tags", { params: { limit } });
  allCache = data;
  return allCache;
}
