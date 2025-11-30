import { Focusable, ConfirmModal, showModal } from "@decky/ui";
import { FaInfoCircle } from "react-icons/fa";

interface PlainButtonProps {
  label: string;
  description?: string;
  value: string;

  modalTitle?: string;
  modalDesc?: string;

  onClick?: () => void;
}

export function PlainButton({
  label,
  description,
  value,
  modalTitle,
  modalDesc,
  onClick,
}: PlainButtonProps) {
  const handleClick = () => {
    if (modalTitle) {
      showModal(
        <ConfirmModal
          strTitle={
            <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "22px" }}>
              <FaInfoCircle size={22} />
              <span>{modalTitle}</span>
            </div>
          }
          strDescription={modalDesc ?? ""}
          strOKButtonText="Close"
          onOK={() => {}}
          bAlertDialog={true}
        />
      );
    }

    if (onClick) onClick();
  };

  return (
    <Focusable
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "10px 10px",
        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
        cursor: "pointer",
        fontSize: "16px",
      }}
      onActivate={handleClick}
    >
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span>{label}</span>
        {description && (
          <span
            style={{
              opacity: 0.6,
              fontSize: "13px",
              marginTop: "3px",
              paddingRight: "20px",
            }}
          >
            {description}
          </span>
        )}
      </div>

      <span style={{ opacity: 0.7 }}>{value}</span>
    </Focusable>
  );
}
