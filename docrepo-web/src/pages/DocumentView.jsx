import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link as RouterLink } from "react-router-dom";
import {
  Box, Stack, Paper, Typography, Chip, Divider, IconButton, Button, Tooltip,
  Alert, Snackbar, Table, TableHead, TableRow, TableCell, TableBody, LinearProgress, TextField, Autocomplete
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import ShieldIcon from "@mui/icons-material/Shield";
import { VisibilityChip } from "../components/document/VisibilityChip";
import EditMetaDialog from "../components/document/EditMetaDialog";
import UploadVersionDialog from "../components/document/UploadVersionDialog";
import PermissionsDialog from "../components/document/PermissionsDialog";

import api from "../api/client";
import { searchTags } from "../api/tags";

function prettyBytes(n) {
  if (!n && n !== 0) return "";
  const u = ["B","KB","MB","GB"]; let i=0,v=n||0; while(v>=1024&&i<u.length-1){v/=1024;i++;} return `${v.toFixed(v<10&&i>0?1:0)} ${u[i]}`;
}

export default function DocumentView() {
  const { id } = useParams();
  const docId = Number(id);
  const nav = useNavigate();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [details, setDetails] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState("");

  const [tagOptions, setTagOptions] = useState([]);
  const [tagInput, setTagInput] = useState("");
  const [addingTag, setAddingTag] = useState(false);

  const [editOpen, setEditOpen] = useState(false);
  const [versOpen, setVersOpen] = useState(false);
  const [permOpen, setPermOpen] = useState(false);

  // --- API helpers
  async function getDetails() { return (await api.get(`/documents/${docId}`)).data; }
  async function getVersions() { return (await api.get(`/documents/${docId}/versions`)).data; }
  async function patchMeta(payload) { return (await api.patch(`/documents/${docId}`, payload)).data; }
  async function download(version) { return (await api.get(`/documents/${docId}/download`, { params: version ? { version } : {} })).data.url; }
  async function uploadVersion(file, onProgress) {
    const fd = new FormData(); fd.append("file", file);
    await api.post(`/documents/${docId}/versions`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (evt) => evt.total && onProgress(Math.round((evt.loaded/evt.total)*100)),
    });
     await refresh();
  }
  async function delDoc() { await api.delete(`/documents/${docId}`); }
  async function addTag(tag_id) { await api.put(`/documents/${docId}/tags`, { tag_id }); }
  async function removeTag(tag_id) { await api.delete(`/documents/${docId}/tags`, { data: { tag_id } }); }
  async function createTag(name) { return (await api.post(`/tags`, { name })).data; }
  async function listDepartments() { return (await api.get(`/departments`)).data; }
  async function listPerms() { return (await api.get(`/documents/${docId}/permissions`)).data; }
  async function replacePerms(departments) { return (await api.put(`/documents/${docId}/permissions`, { departments })).data; }

  // load details + versions
  async function refresh() {
    setLoading(true); setErr("");
    try {
      const [d, v] = await Promise.all([getDetails(), getVersions()]);
      setDetails(d); setVersions(v);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed to load document.");
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, [docId]);

  // tag typeahead
  useEffect(() => {
    let alive = true;
    (async () => { try { const rows = await searchTags(tagInput, 20); if (alive) setTagOptions(rows || []); } catch { if (alive) setTagOptions([]); }})();
    return () => { alive = false; };
  }, [tagInput]);

  if (!details) {
    return <Paper sx={{ p: 3 }}>{err ? <Alert severity="error">{err}</Alert> : <LinearProgress />}</Paper>;
  }

  const canEdit = !!details.perms?.can_edit;
  const canModify = !!details.perms?.can_modify;

  const bg = isDark
    ? "linear-gradient(135deg, rgba(14,165,233,.10), rgba(124,58,237,.10))"
    : "linear-gradient(135deg, rgba(25,118,210,.08), rgba(123,31,162,.08))";

  async function handleDownload(version) {
    const url = await download(version);
    window.location.href = url;
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${details.doc.title}"? This cannot be undone.`)) return;
    try { await delDoc(); setToast("Document deleted."); nav("/documents", { replace: true }); }
    catch (e) { setErr(e?.response?.data?.detail || "Delete failed."); }
  }

  async function handleAddTag(val) {
    setAddingTag(true);
    try {
      const name = typeof val === "string" ? val.trim() : (val?.name || "").trim();
      if (!name) return;
      let tagId = (typeof val !== "string" && val?.tag_id) ? val.tag_id : undefined;
      if (!tagId) tagId = (await createTag(name)).tag_id;
      await addTag(tagId);
      await refresh();
      setToast(`Tag "${name}" added.`);
    } finally { setAddingTag(false); }
  }

  async function handleRemoveTagByName(name) {
    const match = tagOptions.find((t) => t.name === name) || (await searchTags(name, 1))?.[0];
    if (!match?.tag_id) return;
    await removeTag(match.tag_id);
    await refresh();
    setToast(`Tag "${name}" removed.`);
  }

  return (
    <Stack spacing={2}>
      <Snackbar open={!!toast} onClose={() => setToast("")} autoHideDuration={2800} message={toast}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }} />

      {/* Header + actions */}
      <Paper sx={{ p: { xs: 2, md: 3 }, borderRadius: 3, background: bg, border: (t) => `1px solid ${t.palette.divider}` }}>
        <Stack direction="row" alignItems="flex-start" spacing={2} justifyContent="space-between">
          <Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h5" fontWeight={800}>{details.doc.title}</Typography>
              <VisibilityChip value={details.doc.visibility} />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>
              Updated: {new Date(details.doc.updated_at).toLocaleString()}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button onClick={() => handleDownload()} variant="outlined" startIcon={<DownloadIcon />}>Download</Button>
            <Button onClick={() => setEditOpen(true)} variant="outlined" startIcon={<EditIcon />} disabled={!canEdit}>Edit</Button>
            <Button onClick={() => setVersOpen(true)} variant="outlined" startIcon={<AddIcon />} disabled={!canEdit}>New Version</Button>
            <Button onClick={() => setPermOpen(true)} variant="outlined" startIcon={<ShieldIcon />}>Permissions</Button>
            <Button onClick={handleDelete} color="error" variant="contained" startIcon={<DeleteIcon />} disabled={!canModify}>Delete</Button>
          </Stack>
        </Stack>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2" sx={{ mb: .5 }}>Description</Typography>
        <Typography variant="body1">{details.doc.description || "—"}</Typography>

        {/* Tags */}
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>
          {(details.tags || []).map((t) => (
            <Chip key={t} label={t} size="small" color="primary" variant="outlined"
              onDelete={canEdit ? () => handleRemoveTagByName(t) : undefined}
              sx={{ mr: .5, mb: .5, fontWeight: 700 }} />
          ))}
          {canEdit && (
            <Autocomplete size="small" options={tagOptions} sx={{ minWidth: 220 }}
              getOptionLabel={(o) => (typeof o === "string" ? o : (o?.name || ""))}
              filterOptions={(x) => x} freeSolo
              onInputChange={(_, v) => setTagInput(v)}
              onChange={(_, val) => val && handleAddTag(val)}
              renderInput={(params) => <TextField {...params} label="Add tag…" disabled={addingTag} />}
            />
          )}
        </Stack>
      </Paper>

      {/* Versions */}
      <Paper sx={{ p: { xs: 2, md: 3 } }}>
        <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>Version history</Typography>
        {loading && <LinearProgress sx={{ mb: 2 }} />}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Version</TableCell>
              <TableCell>Uploaded</TableCell>
              <TableCell>Size</TableCell>
              <TableCell>Uploaded by</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(versions || []).map((v) => (
              <TableRow key={v.version_no} hover selected={v.is_latest}>
                <TableCell>v{v.version_no}{v.is_latest ? " (latest)" : ""}</TableCell>
                <TableCell>{new Date(v.uploaded_at).toLocaleString()}</TableCell>
                <TableCell>{prettyBytes(v.file_size)}</TableCell>
                <TableCell>{v.uploaded_by_email || `#${v.uploaded_by}`}</TableCell>
                <TableCell align="right">
                  <Tooltip title="Download this version">
                    <IconButton size="small" onClick={() => handleDownload(v.version_no)}>
                      <DownloadIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {(!versions || versions.length === 0) && (
              <TableRow><TableCell colSpan={5} align="center" sx={{ py: 4, color: "text.secondary" }}>No versions.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      {err && <Alert severity="error" onClose={() => setErr("")}>{err}</Alert>}

      {/* dialogs */}
      <EditMetaDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        initial={details.doc}
        onSave={async (payload) => {
          const updated = await patchMeta(payload);
          setDetails((d) => ({ ...d, doc: updated }));
          setToast("Metadata updated.");
        }}
      />
      <UploadVersionDialog
        open={versOpen}
        onClose={() => setVersOpen(false)}
        onUpload={uploadVersion}
      />
      <PermissionsDialog
        open={permOpen}
        onClose={() => setPermOpen(false)}
        loadData={async () => ({ departments: await listDepartments(), rows: await listPerms() })}
        saveData={async (rows) => { await replacePerms(rows); setToast("Permissions saved."); }}
      />
    </Stack>
  );
}
