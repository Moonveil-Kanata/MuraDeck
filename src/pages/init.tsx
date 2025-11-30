import {
  ButtonItem,
  Navigation,
  SideMenu
} from "@decky/ui";
import { FaExclamationCircle } from "react-icons/fa";

import { ParallelPanelSection } from "../components/styles/parallelPanelSec";

const PerformanceIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg width="18" height="18" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M17.9999 33.0001C26.2841 33.0001 32.9998 26.2843 32.9998 18C32.9998 9.71574 26.2841 3 17.9999 3C9.71569 3 3 9.71574 3 18C3 26.2843 9.71569 33.0001 17.9999 33.0001ZM16.4637 19.3522L14.0785 28.3003L24.9361 16.0935H19.7223L21.6775 7.62115L11.25 19.3522H16.4637Z"
      fill="currentColor"
    />
  </svg>
);

export function InfoTab() {
  return (
    <>
      <ParallelPanelSection title="Welcome to Mura Deck">
        <div style={{ display: "flex", gap: "8px" }}>
          <FaExclamationCircle style={{ paddingTop: "4px", color: "#ffef8aff" }} />
          <span>
            If your device is <b>refurbished</b>, unfortunately it won't work
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <FaExclamationCircle style={{ paddingTop: "4px", color: "#ffef8aff" }} />
          <span>
            Internet connection required
          </span>
        </div>
      </ParallelPanelSection>
      <ParallelPanelSection title="Initialization">
        <div style={{ display: "flex", gap: "8px" }}>
          <FaExclamationCircle style={{ paddingTop: "4px", color: "#a8beffff" }} />
          <span>
            <b>Disable mura compensation</b> before using this plugin
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <FaExclamationCircle style={{ paddingTop: "4px", color: "#a8beffff" }} />
          <span>
            And, make sure <b>Scaling Filter</b> isn't <b>Sharp</b> or <b>Pixel</b>
          </span>
        </div>
        <ButtonItem label="Enable Developer Mode" layout="inline" onClick={() => { Navigation.Navigate("/settings/system") }}>
          Settings
        </ButtonItem>
        <ButtonItem label="Disable Mura Compensation" layout="inline" onClick={() => { Navigation.Navigate("/settings/developer") }}>
          Developer
        </ButtonItem>
        <ButtonItem
          label={
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              Go to <PerformanceIcon /> set <b>Scaling Filter</b> to <b>LINEAR</b>
            </div>
          }
          layout="inline"
          onClick={() => {
            Navigation.OpenSideMenu(SideMenu.QuickAccess);
          }}
        >
          •••
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
