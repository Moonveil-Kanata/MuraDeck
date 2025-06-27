import {
  ButtonItem,
  Navigation,
  SideMenu
} from "@decky/ui";
import { FaExclamationCircle } from "react-icons/fa";
import { ParallelPanelSection } from "../components/styles/parallelPanelSec";

export function InfoTab() {
  return (
    <>
      <ParallelPanelSection title= "Welcome to Mura Deck">
        <div style={{ display: "flex", gap: "8px"}}>
          <FaExclamationCircle style={{paddingTop: "4px"}}/>
          <span>
            Make sure you're on <b>SteamOS 3.7.8</b> or above for better ReShade performance.
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px"}}>
          <FaExclamationCircle style={{paddingTop: "4px"}}/>
          <span>
            And, <b>disable mura compensation</b> before using this plugin.
          </span>
        </div>
      </ParallelPanelSection>
      <ParallelPanelSection title="Initialization">
        <ButtonItem label="Enable Developer Mode" layout="inline" onClick={() => { Navigation.Navigate("/settings/system") }}>
          System Settings
        </ButtonItem>
        <ButtonItem label="Disable Mura Compensation" layout="inline" onClick={() => { Navigation.Navigate("/settings/developer") }}>
          Developer Menu
        </ButtonItem>
        <ButtonItem layout="below" onClick={() => {
          Navigation.NavigateBack();
          Navigation.OpenSideMenu(SideMenu.QuickAccess);
        }}>
          Done
        </ButtonItem>
      </ParallelPanelSection>
    </>
  );
}
