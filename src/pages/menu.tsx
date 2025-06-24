import { SidebarNavigation } from "@decky/ui";
import { FaInfoCircle, FaListAlt } from "react-icons/fa";
import { StatusTab } from "./status";
import { InfoTab } from "./welcome";

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
            title: "Welcome",
            icon: <FaListAlt />,
            route: "/mura-deck/menu/welcome",
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
