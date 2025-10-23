// src/api/tags.js
import api from "./client";

let cache = new Map(); // key = `${prefix}|${limit}` -> [{ tag_id, name }]
let allCache = null;

export async function searchTags(prefix = "", limit = 20) {
  const key = `${prefix}|${limit}`;
  if (cache.has(key)) return cache.get(key);

  const params = prefix ? { q: prefix, limit } : { limit };
  const { data } = await api.get("/tags", { params });

  cache.set(key, data);
  return data;
}

export async function listAllTags(limit = 200) {
  if (allCache) return allCache;
  const { data } = await api.get("/tags", { params: { limit } });
  allCache = data;
  return allCache;
}

/**
 * Create (or get) a tag by name.
 * Backend is idempotent: returns the existing tag if name already exists (case-insensitive).
 * Returns: { tag_id, name }
 */
export async function createTag(name) {
  const norm = String(name ?? "")
    .trim()
    .replace(/\s+/g, " ");
  if (!norm) throw new Error("Tag name must not be empty.");

  const { data } = await api.post("/tags", { name: norm });

  // Invalidate local caches so the new tag appears in typeahead immediately.
  cache.clear();
  allCache = null;

  return data; // { tag_id, name }
}
