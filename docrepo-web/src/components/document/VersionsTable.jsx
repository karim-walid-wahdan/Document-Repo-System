import { Table, TableHead, TableRow, TableCell, TableBody, IconButton, Tooltip, Typography } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";

function prettyBytes(n) {
  if (!n && n !== 0) return "";
  const u = ["B", "KB", "MB", "GB"]; let i = 0, v = n || 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

export default function VersionsTable({ rows, onDownload }) {
  return (
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
        {(rows || []).map((v) => (
          <TableRow key={v.version_no} hover selected={v.is_latest}>
            <TableCell>v{v.version_no}{v.is_latest ? " (latest)" : ""}</TableCell>
            <TableCell>{new Date(v.uploaded_at).toLocaleString()}</TableCell>
            <TableCell>{prettyBytes(v.file_size)}</TableCell>
            <TableCell>#{v.uploaded_by}</TableCell>
            <TableCell align="right">
              <Tooltip title="Download this version">
                <IconButton size="small" onClick={() => onDownload(v.version_no)}>
                  <DownloadIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </TableCell>
          </TableRow>
        ))}
        {(!rows || rows.length === 0) && (
          <TableRow>
            <TableCell colSpan={5} align="center" sx={{ py: 4, color: "text.secondary" }}>
              <Typography>No versions found.</Typography>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
