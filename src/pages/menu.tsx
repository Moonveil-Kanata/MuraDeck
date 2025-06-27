import { SidebarNavigation } from "@decky/ui";
import { FaInfoCircle, FaListAlt } from "react-icons/fa";
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
            icon: <FaListAlt />,
            route: "/mura-deck/menu/initialization",
            content: <InfoTab />,
          },
          {
            title: "Status",
            icon: <FaInfoCircle />,
            route: "/mura-deck/menu/status",
            content: <StatusTab />,
          },
        ]}
      />
    </div>
  );
}
