import { SidebarNavigation } from "@decky/ui";
import { FaPollH, FaRocket } from "react-icons/fa";
import { StatusTab } from "./status";
import { InfoTab } from "./init";

export function Menu() {
  return (
    <div
      style={{
        height: "100%",
        marginBottom: "var(--gamepadui-current-footer-height)",
      }}
    >
      <SidebarNavigation
        pages={[
          {
            title: "Initialization",
            icon: <FaRocket />,
            route: "/mura-deck/menu/initialization",
            content: <InfoTab />,
          },
          {
            title: "Status",
            icon: <FaPollH />,
            route: "/mura-deck/menu/status",
            content: <StatusTab />,
          },
        ]}
      />
    </div>
  );
}
