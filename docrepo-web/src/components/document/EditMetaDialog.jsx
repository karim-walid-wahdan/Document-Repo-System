import { useEffect, useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Stack, TextField, MenuItem, Typography, Button, Alert } from "@mui/material";
import PublicIcon from "@mui/icons-material/Public";
import GroupsIcon from "@mui/icons-material/Groups";
import LockIcon from "@mui/icons-material/Lock";
import EditIcon from "@mui/icons-material/Edit";
import CloseIcon from "@mui/icons-material/Close";

const VIS_OPTIONS = [
  { value: "public",     label: "public",     Icon: PublicIcon,  paletteKey: "success"  },
  { value: "internal",   label: "internal",   Icon: GroupsIcon,  paletteKey: "info"     },
  { value: "restricted", label: "restricted", Icon: LockIcon,    paletteKey: "warning"  },
];

export default function EditMetaDialog({ open, doc, onClose, onSave }) {
  const [title, setTitle] = useState(doc?.title || "");
  const [description, setDescription] = useState(doc?.description || "");
  const [visibility, setVisibility] = useState(doc?.visibility || "internal");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setTitle(doc?.title || "");
      setDescription(doc?.description || "");
      setVisibility(doc?.visibility || "internal");
      setError("");
    }
  }, [open, doc]);

  async function save() {
    setError("");
    if (!title.trim()) { setError("Title is required."); return; }
    try {
      setSaving(true);
      await onSave({ title: title.trim(), description, visibility });
      onClose();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to save.");
    } finally { setSaving(false); }
  }

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Edit metadata</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} fullWidth multiline minRows={3} />
          <TextField select label="Visibility" value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            {VIS_OPTIONS.map((opt) => {
              const I = opt.Icon;
              return (
                <MenuItem key={opt.value} value={opt.value}>
                  <I sx={{ color: (t) => t.palette[opt.paletteKey].main, mr: 1 }} fontSize="small" />
                  <Typography sx={{ textTransform: "capitalize" }}>{opt.label}</Typography>
                </MenuItem>
              );
            })}
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving} startIcon={<CloseIcon />}>Cancel</Button>
        <Button onClick={save} disabled={saving} variant="contained" startIcon={<EditIcon />}>Save</Button>
      </DialogActions>
    </Dialog>
  );
}
