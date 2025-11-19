import { Focusable } from "@decky/ui";

interface PlainButtonProps {
  label: string;
  description?: string;
  value: string;
  onClick?: () => void;
}

export function PlainButton({ label, description, value, onClick }: PlainButtonProps) {
  return (
    <Focusable
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "10px 10px",
        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
        cursor: onClick ? "pointer" : "default",
        fontSize: "16px",
      }}
      onActivate={onClick}
    >
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span>{label}</span>
        {description && (
          <span style={{ opacity: 0.6, fontSize: "13px", marginTop: "3px", paddingRight: "20px" }}>
            {description}
          </span>
        )}
      </div>

      <span style={{ opacity: 0.7 }}>{value}</span>
    </Focusable>
  );
}
