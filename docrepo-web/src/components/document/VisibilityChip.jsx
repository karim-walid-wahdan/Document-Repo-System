import { Chip } from "@mui/material";
import PublicIcon from "@mui/icons-material/Public";
import GroupsIcon from "@mui/icons-material/Groups";
import LockIcon from "@mui/icons-material/Lock";

const MAP = {
  public:     { Icon: PublicIcon,  paletteKey: "success"  },
  internal:   { Icon: GroupsIcon,  paletteKey: "info"     },
  restricted: { Icon: LockIcon,    paletteKey: "warning"  },
};

export default function VisibilityChip({ value }) {
  const m = MAP[value] || MAP.internal;
  return (
    <Chip
      size="small"
      icon={<m.Icon sx={{ color: (t) => t.palette[m.paletteKey].main }} />}
      label={value}
      variant="outlined"
      sx={{ fontWeight: 700, textTransform: "capitalize" }}
    />
  );
}
