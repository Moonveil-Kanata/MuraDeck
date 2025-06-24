import { FC, ReactNode } from "react";
import { Focusable, ConfirmModal, showModal } from "@decky/ui";
import { Desc, EffectKey } from "../defines/descriptor";

interface EffectInfoProps {
  effectKey: EffectKey;
  children: ReactNode;
}

export const EffectInfo: FC<EffectInfoProps> = ({ effectKey, children }) => {
  const { title, desc, icon: Icon } = Desc[effectKey];

  return (
    <Focusable
      onMenuActionDescription="More Info"
      onMenuButton={() =>
        showModal(
          <ConfirmModal
            strTitle={
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '22px' }}>
                {Icon && <Icon size={24} />}
                <span>{title}</span>
              </div>
            }
            strDescription={desc}
            strOKButtonText="Close"
            onOK={() => {}}
            bAlertDialog={true}
          />
        )
      }
    >
      {children}
    </Focusable>
  );
};
