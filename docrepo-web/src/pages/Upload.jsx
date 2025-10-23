import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box, Paper, Stack, Typography, TextField, MenuItem,
  Chip, LinearProgress, Alert, Button, IconButton,
  InputAdornment, Tooltip, Divider, Snackbar
} from "@mui/material";
import Autocomplete from "@mui/material/Autocomplete";
import { useTheme } from "@mui/material/styles";

import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import PublicIcon from "@mui/icons-material/Public";
import GroupsIcon from "@mui/icons-material/Groups";
import LockIcon from "@mui/icons-material/Lock";

import { createDocument } from "../api/documents";
import { searchTags } from "../api/tags";

/* --- config/helpers --- */
const MAX_MB = 100;
const VIS_OPTIONS = [
  { value: "public",     label: "public",     Icon: PublicIcon, paletteKey: "success"  },
  { value: "internal",   label: "internal",   Icon: GroupsIcon, paletteKey: "info"     },
  { value: "restricted", label: "restricted", Icon: LockIcon,   paletteKey: "warning"  },
];

function prettyBytes(n) {
  if (!n && n !== 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0, v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

export default function Upload() {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  // form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState("internal");
  const [tags, setTags] = useState([]);        // [{tag_id?, name}] or string (freeSolo)
  const [tagInput, setTagInput] = useState("");
  const [tagOptions, setTagOptions] = useState([]);
  const [file, setFile] = useState(null);

  // ui state
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fileInputRef = useRef(null);

  // typeahead for tags
  useEffect(() => {
    let ok = true;
    (async () => {
      try {
        const rows = await searchTags(tagInput, 20);
        if (ok) setTagOptions(rows);
      } catch {
        if (ok) setTagOptions([]);
      }
    })();
    return () => { ok = false; };
  }, [tagInput]);

  // normalize tags -> array of names
  const tagNames = useMemo(
    () =>
      (tags || [])
        .map((t) => (typeof t === "string" ? t.trim() : (t?.name || "").trim()))
        .filter(Boolean),
    [tags]
  );

  function pickFile() { fileInputRef.current?.click(); }
  function onFileChange(e) { const f = e.target.files?.[0]; if (f) setFile(f); }

  // drag-drop
  function handleDrop(e) {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    const f = e.dataTransfer.files?.[0]; if (f) setFile(f);
  }
  function handleDragOver(e) { e.preventDefault(); e.stopPropagation(); setDragOver(true); }
  function handleDragLeave(e) { e.preventDefault(); e.stopPropagation(); setDragOver(false); }

  // validations
  function validate() {
    if (!title.trim()) return "Title is required.";
    if (!file) return "Please choose a file to upload.";
    if (file.name.toLowerCase().endsWith(".exe")) return "Executable files are not allowed.";
    if (file.size > MAX_MB * 1024 * 1024) return `File is too large. Max ${MAX_MB} MB.`;
    return "";
  }

  async function submit() {
    setError("");
    const msg = validate();
    if (msg) { setError(msg); return; }

    setBusy(true); setProgress(0);
    try {
      await createDocument({
        title: title.trim(),
        description,
        visibility,
        tagNames,
        file,
        onProgress: (p) => setProgress(p),
      });

      // reset
      setTitle(""); setDescription(""); setTags([]); setFile(null);
      setProgress(0); setSuccess("Upload complete! A new document/version has been created.");
    } catch (e) {
      const apiMsg = e?.response?.data?.detail;
      setError(apiMsg || "Upload failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const bg = isDark
    ? "linear-gradient(135deg, rgba(14,165,233,.12), rgba(124,58,237,.12))"
    : "linear-gradient(135deg, rgba(25,118,210,.10), rgba(123,31,162,.10))";

  return (
    <Stack spacing={2}>
      <Paper
        elevation={0}
        sx={{
          p: { xs: 2, md: 3 },
          borderRadius: 3,
          background: bg,
          border: (t) => `1px solid ${t.palette.divider}`,
        }}
      >
        <Typography variant="h5" fontWeight={800} sx={{ mb: 1 }}>
          Upload a document
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Title is unique. If a document with the same title exists, this creates a new version.
        </Typography>

        <Stack spacing={2} onKeyDown={(e) => { if (e.key === "Enter") submit(); }}>
          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          <Snackbar
            open={!!success}
            autoHideDuration={3500}
            onClose={() => setSuccess("")}
            message={success}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          />

          {/* Title + Visibility */}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              fullWidth
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <Tooltip title="Unique per document; same title creates a new version">
                      <InfoOutlinedIcon fontSize="small" />
                    </Tooltip>
                  </InputAdornment>
                ),
              }}
            />

            <TextField
              select
              label="Visibility"
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              sx={{ minWidth: 220 }}
              SelectProps={{
                renderValue: (value) => {
                  const opt = VIS_OPTIONS.find(o => o.value === value) || VIS_OPTIONS[1];
                  const Ico = opt.Icon;
                  return (
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Ico sx={{ color: (t) => t.palette[opt.paletteKey].main, opacity: 0.9 }} fontSize="small" />
                      <Typography sx={{ textTransform: "capitalize" }}>{opt.label}</Typography>
                    </Stack>
                  );
                },
              }}
            >
              {VIS_OPTIONS.map((opt) => {
                const Ico = opt.Icon;
                return (
                  <MenuItem key={opt.value} value={opt.value}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Ico sx={{ color: (t) => t.palette[opt.paletteKey].main, opacity: 0.9 }} fontSize="small" />
                      <Typography sx={{ textTransform: "capitalize" }}>{opt.label}</Typography>
                    </Stack>
                  </MenuItem>
                );
              })}
            </TextField>
          </Stack>

          {/* Description */}
          <TextField
            label="Description"
            multiline
            minRows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          {/* Tags */}
          <Autocomplete
            multiple
            freeSolo
            options={tagOptions}
            value={tags}
            onChange={(_, val) => setTags(val)}
            onInputChange={(_, val) => setTagInput(val)}
            getOptionLabel={(opt) => (typeof opt === "string" ? opt : opt?.name || "")}
            filterOptions={(x) => x}
            renderInput={(params) => (
              <TextField {...params} label="Tags" placeholder="Type to search or add new…" />
            )}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip
                  key={(typeof option === "string" ? option : option?.name) + index}
                  label={typeof option === "string" ? option : option?.name}
                  color="secondary"
                  variant="outlined"
                  sx={{ fontWeight: 700 }}
                  {...getTagProps({ index })}
                />
              ))
            }
          />

          {/* File drop-zone */}
          <Box
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); }}
            onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); }}
            onDrop={handleDrop}
            onClick={pickFile}
            sx={(t) => ({
              cursor: "pointer",
              borderRadius: 3,
              p: 3,
              border: `2px dashed ${dragOver ? t.palette.primary.main : t.palette.divider}`,
              background: dragOver
                ? (isDark ? "rgba(110,231,255,.08)" : "rgba(25,118,210,.08)")
                : (isDark ? "rgba(255,255,255,.02)" : "rgba(0,0,0,.02)"),
              display: "flex",
              alignItems: "center",
              gap: 2,
            })}
          >
            <CloudUploadIcon />
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                Drag & drop your file here, or click to choose
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Allowed: anything except .exe · Max {MAX_MB} MB (client-side)
              </Typography>
            </Box>

            {file && (
              <Chip
                icon={<InsertDriveFileIcon />}
                label={`${file.name} — ${prettyBytes(file.size)}`}
                variant="outlined"
                color="primary"
              />
            )}

            {file && (
              <Tooltip title="Remove file">
                <IconButton onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                  <DeleteForeverIcon />
                </IconButton>
              </Tooltip>
            )}

            <input ref={fileInputRef} type="file" style={{ display: "none" }} onChange={onFileChange} />
          </Box>

          {busy && (
            <Box>
              <LinearProgress variant="determinate" value={progress} />
              <Typography variant="caption" color="text.secondary">
                Uploading… {progress}%
              </Typography>
            </Box>
          )}

          <Divider />

          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              startIcon={<CloudUploadIcon />}
              onClick={submit}
              disabled={busy}
              sx={(t) => ({
                fontWeight: 800,
                textTransform: "none",
                background:
                  t.palette.mode === "dark"
                    ? "linear-gradient(90deg, #0ea5e9 0%, #7c3aed 100%)"
                    : "linear-gradient(90deg, #1976d2 0%, #7b1fa2 100%)",
                "&:hover": {
                  filter: "brightness(1.05)",
                  background:
                    t.palette.mode === "dark"
                      ? "linear-gradient(90deg, #22d3ee 0%, #8b5cf6 100%)"
                      : "linear-gradient(90deg, #1e88e5 0%, #8e24aa 100%)",
                },
              })}
            >
              Upload
            </Button>

            <Button
              variant="outlined"
              color="inherit"
              onClick={() => { setTitle(""); setDescription(""); setTags([]); setFile(null); setError(""); setSuccess(""); }}
              disabled={busy}
              startIcon={<DeleteForeverIcon />}
            >
              Clear
            </Button>

            {success && (
              <Chip color="success" icon={<CheckCircleIcon />} label="Uploaded" sx={{ ml: "auto", fontWeight: 700 }} />
            )}
          </Stack>
        </Stack>
      </Paper>
    </Stack>
  );
}
