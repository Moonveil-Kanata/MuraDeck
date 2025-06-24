import { Focusable } from "@decky/ui";

interface PlainButtonProps {
  label: string;
  value: string;
  onClick?: () => void;
}

export function PlainButton({ label, value, onClick }: PlainButtonProps) {
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
      <span>{label}</span>
      <span style={{ opacity: 0.7 }}>{value}</span>
    </Focusable>
  );
}
