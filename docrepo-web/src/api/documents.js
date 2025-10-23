import api from "./client";



export async function searchDocumentsAdvanced(opts = {}) {
  const { q, tags = [], uploader } = opts;

  // Build query string with repeated params (?tags=a&tags=b)
  const qs = new URLSearchParams();
  if (q && q.trim()) qs.set("q", q.trim());
  if (uploader != null && String(uploader).trim() !== "") {
    qs.set("uploader", String(uploader));
  }
  if (Array.isArray(tags) && tags.length) {
    tags.filter(Boolean).forEach((t) => qs.append("tags", t));
  }

  const url = qs.toString() ? `/documents?${qs.toString()}` : `/documents`;
  const { data } = await api.get(url);
  return data;
}
export async function getDocumentDetails(docId) {
  const { data } = await api.get(`/documents/${docId}`);
  return data; 
}

export async function deleteDocument(docId) {
  await api.delete(`/documents/${docId}`);
}

export async function updateDocumentMeta(docId, payload) {
  const { data } = await api.patch(`/documents/${docId}`, payload);
  return data;
}

export async function addVersion(docId, file) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post(`/documents/${docId}/versions`, fd);
  return data;
}

export async function createDocument({ title, description, visibility, tagNames, file, onProgress }) {
  const fd = new FormData();
  fd.append("title", title);
  fd.append("description", description || "");
  fd.append("visibility", visibility || "internal");
  fd.append("tags", (tagNames || []).join(","));
  fd.append("file", file);

  const { data } = await api.post("/documents", fd, {
    onUploadProgress: onProgress
      ? (evt) => {
          if (!evt.total) return;
          const pct = Math.round((evt.loaded / evt.total) * 100);
          onProgress(pct);
        }
      : undefined,
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data; // VersionOut
}


export async function getPresignedDownload(docId, version) {
  const { data } = await api.get(`/documents/${docId}/download`, {
    params: version ? { version } : undefined,
  });
  return data.url;
}




export async function getVersionHistory(id) {
  const { data } = await api.get(`/documents/${id}/versions`);
  return data; // [VersionOut...]
}
export async function updateDocument(id, payload) {
  const { data } = await api.patch(`/documents/${id}`, payload);
  return data; // DocumentOut
}
export async function downloadDocument(id, version) {
  const { data } = await api.get(`/documents/${id}/download`, { params: version ? { version } : {} });
  return data.url; // presigned URL
}
export async function uploadVersion(id, file, onProgress) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post(`/documents/${id}/versions`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (!evt.total || !onProgress) return;
      onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
  });
  return data; // VersionOut
}


// tags on a doc
export async function addDocTag(id, tag_id) {
  await api.put(`/documents/${id}/tags`, { tag_id });
}
export async function removeDocTag(id, tag_id) {
  await api.delete(`/documents/${id}/tags`, { data: { tag_id } });
}

// permissions
export async function listPermissions(id) {
  const { data } = await api.get(`/documents/${id}/permissions`);
  return data; // [{department_id, level}]
}
export async function replacePermissions(id, departments) {
  const { data } = await api.put(`/documents/${id}/permissions`, { departments });
  return data;
}