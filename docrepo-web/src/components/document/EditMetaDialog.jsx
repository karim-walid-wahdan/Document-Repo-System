import React, { useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Stack, TextField, Button, Alert
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import EditIcon from "@mui/icons-material/Edit";
import { VisibilitySelect } from "./VisibilityChip";

export default function EditMetaDialog({ open, onClose, initial, onSave }) {
  const [title, setTitle] = useState(initial?.title || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [visibility, setVisibility] = useState(initial?.visibility || "internal");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setTitle(initial?.title || "");
      setDescription(initial?.description || "");
      setVisibility(initial?.visibility || "internal");
      setError("");
    }
  }, [open, initial]);

  async function save() {
    setError("");
    if (!title.trim()) { setError("Title is required."); return; }
    setSaving(true);
    try {
      await onSave({ title: title.trim(), description, visibility });
    } catch (e) {
      setError(e?.message || "Failed to save.");
      return;
    } finally { setSaving(false); }
    onClose();
  }

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Edit metadata</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} fullWidth multiline minRows={3} />
          <VisibilitySelect value={visibility} onChange={setVisibility} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving} startIcon={<CloseIcon />}>Cancel</Button>
        <Button onClick={save} disabled={saving} variant="contained" startIcon={<EditIcon />}>Save</Button>
      </DialogActions>
    </Dialog>
  );
}
