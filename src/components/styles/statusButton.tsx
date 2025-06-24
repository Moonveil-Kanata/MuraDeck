import { FC, ReactNode } from "react";
import { Field, quickAccessControlsClasses, Focusable, Navigation } from "@decky/ui";

interface StatusButtonProps {
  label: string;
  description?: string;
  icon?: ReactNode;
  route: string;
  bottomSeparator?: "standard" | "thick" | "none";
  disabled?: boolean;
}

export const StatusButton: FC<StatusButtonProps> = ({
  label,
  description,
  icon,
  route,
  bottomSeparator = "standard",
  disabled = false
}) => {
  return (
    <div className={`qam-focusable-item ${quickAccessControlsClasses.PanelSectionRow}`}>
      <Field
        bottomSeparator={bottomSeparator}
        description={
          <Focusable
            onActivate={() => {
              if (!disabled) Navigation.Navigate(route);
            }}
            onOKActionDescription={disabled ? "" : "Open"}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              width: "100%",
              paddingBottom: 8,
              opacity: disabled ? 0.4 : 1,
              pointerEvents: disabled ? "none" : "auto",
            }}
          >
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  fontWeight: "bold",
                  textTransform: "uppercase",
                  fontSize: "16px",
                }}
              >
                {label}
              </div>
              {description && (
                <div
                  style={{
                    fontSize: "14px",
                    color: "rgba(255, 255, 255, 0.5)",
                    marginTop: 2,
                  }}
                >
                  {description}
                </div>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", paddingRight: 16 }}>
              {icon}
            </div>
          </Focusable>
        }
      />
    </div>
  );
};