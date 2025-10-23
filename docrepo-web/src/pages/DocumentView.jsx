import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Paper, Stack, Snackbar, Alert, LinearProgress, Typography } from "@mui/material";
import DocHeader from "../components/document/DocHeader";
import VersionsTable from "../components/document/VersionsTable";
import EditMetaDialog from "../components/document/EditMetaDialog";
import UploadVersionDialog from "../components/document/UploadVersionDialog";
import PermissionsDialog from "../components/document/PermissionsDialog";
import {
  getDocumentDetails, getVersionHistory, downloadDocument, updateDocument,
  uploadVersion, deleteDocument, listPermissions, replacePermissions,
  addDocTag, removeDocTag
} from "../api/documents";
import { searchTags, createTag } from "../api/tags";

export default function DocumentView() {
  const { id } = useParams();
  const docId = Number(id);
  const nav = useNavigate();

  const [details, setDetails] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [versOpen, setVersOpen] = useState(false);
  const [permOpen, setPermOpen] = useState(false);

  async function refresh() {
    setLoading(true); setErr("");
    try {
      const [d, v] = await Promise.all([getDocumentDetails(docId), getVersionHistory(docId)]);
      setDetails(d); setVersions(v);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed to load document.");
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, [docId]);

  if (!details) {
    return (
      <Paper sx={{ p: 3 }}>
        {err ? <Alert severity="error">{err}</Alert> : <LinearProgress />}
      </Paper>
    );
  }

  // header actions
  const handleDownload = async (ver) => {
    const url = await downloadDocument(docId, ver);
    window.location.href = url;
  };
  const handleDelete = async () => {
    if (!window.confirm(`Delete "${details.doc.title}"? This cannot be undone.`)) return;
    try {
      await deleteDocument(docId);
      setToast("Document deleted.");
      nav("/documents", { replace: true });
    } catch (e) { setErr(e?.response?.data?.detail || "Delete failed."); }
  };

  return (
    <Stack spacing={2}>
      <Snackbar open={!!toast} onClose={() => setToast("")} autoHideDuration={2800}
        message={toast} anchorOrigin={{ vertical: "bottom", horizontal: "right" }} />

      <DocHeader
        details={details}
        onDownload={() => handleDownload(undefined)}
        onEdit={() => setEditOpen(true)}
        onNewVersion={() => setVersOpen(true)}
        onPermissions={() => setPermOpen(true)}
        onDelete={handleDelete}
      />

      <Paper sx={{ p: { xs: 2, md: 3 } }}>
        <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>Version history</Typography>
        {loading && <LinearProgress sx={{ mb: 2 }} />}
        <VersionsTable rows={versions} onDownload={handleDownload} />
      </Paper>

      {err && <Alert severity="error" onClose={() => setErr("")}>{err}</Alert>}

      {/* dialogs */}
      <EditMetaDialog
        open={editOpen}
        doc={details.doc}
        onClose={() => setEditOpen(false)}
        onSave={async (payload) => {
          const updated = await updateDocument(docId, payload);
          setDetails((d) => ({ ...d, doc: updated }));
          setToast("Metadata updated.");
        }}
      />

      <UploadVersionDialog
        open={versOpen}
        onClose={() => setVersOpen(false)}
        onUpload={async (file, setProgress) => {
          await uploadVersion(docId, file, setProgress);
          setToast("New version uploaded.");
          await refresh();
        }}
      />

      <PermissionsDialog
        open={permOpen}
        onClose={() => setPermOpen(false)}
        load={async () => ({ rows: await listPermissions(docId) })}
        save={async (rows) => { await replacePermissions(docId, rows); setToast("Permissions saved."); }}
      />
    </Stack>
  );
}
