import { ReactNode } from "react";

interface ParallelPanelSectionProps {
  title?: string;
  children: ReactNode;
  style?: React.CSSProperties;
}

export function ParallelPanelSection({ title, children, style }: ParallelPanelSectionProps) {
  return (
    <div style={{ marginBottom: "16px", ...style }}>
      {title && (
        <div style={{ padding: "8px 0", fontSize: "16px", fontWeight: "bold", textTransform: "uppercase", color: "rgba(255, 255, 255, 0.6)" }}>
          {title}
        </div>
      )}
      <div style={{ padding: 0 }}>{children}</div>
    </div>
  );
}
