import { useEffect, useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Stack, Button, Chip, LinearProgress, Alert } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";

function prettyBytes(n) {
  if (!n && n !== 0) return "";
  const u = ["B", "KB", "MB", "GB"]; let i = 0, v = n || 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

export default function UploadVersionDialog({ open, onClose, onUpload }) {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (!open) { setFile(null); setProgress(0); setError(""); setBusy(false);} }, [open]);

  async function submit() {
    setError("");
    if (!file) { setError("Choose a file."); return; }
    if (file.name.toLowerCase().endsWith(".exe")) { setError("Executable files are not allowed."); return; }
    setBusy(true);
    try {
      await onUpload(file, setProgress);
      onClose();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to upload.");
    } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Upload new version</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          <Button variant="outlined" component="label" startIcon={<CloudUploadIcon />} disabled={busy}>
            Choose file
            <input hidden type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </Button>
          {file && (
            <Chip icon={<InsertDriveFileIcon />} label={`${file.name} — ${prettyBytes(file.size)}`} variant="outlined" color="primary" />
          )}
          {busy && <LinearProgress variant="determinate" value={progress} />}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy} startIcon={<CloseIcon />}>Cancel</Button>
        <Button onClick={submit} disabled={busy} variant="contained" startIcon={<AddIcon />}>Upload</Button>
      </DialogActions>
    </Dialog>
  );
}
