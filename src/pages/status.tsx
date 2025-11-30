import {ButtonItem} from "@decky/ui";
import { call, addEventListener, removeEventListener } from "@decky/api";

import { PlainButton } from "../components/styles/plainButton";
import { ParallelPanelSection } from "../components/styles/parallelPanelSec";
import { DisplayMode } from "../hooks/displayMode";
import { useState, useEffect } from "react";

import {
  PLUGIN_NAME,
  PLUGIN_VERSION,
  PLUGIN_AUTHOR
} from "../utils/rollup";

export function StatusTab() {
  const displayMode = DisplayMode();
  const [shaderInstalled, setShaderInstalled] = useState<boolean | null>(null);
  const [installing, setInstalling] = useState(false);

  const [externalMonitor, setExternalMonitor] = useState<boolean | null>(null);

  useEffect(() => {
    const fetchShaderStatus = async () => {
      const installed = await call<[], boolean>("check_shader_status");
      setShaderInstalled(installed);
    };

    const fetchMonitorStatus = async () => {
      try {
        const isExt = await call<[], boolean>("is_external_display");
        setExternalMonitor(isExt);
      } catch {
        setExternalMonitor(null);
      }
    };

    const handleMonitorChange = (_: any, isExt: boolean) => {
      setExternalMonitor(isExt);
    };

    fetchShaderStatus();
    fetchMonitorStatus();

    addEventListener("monitor_changed", handleMonitorChange);
    return () => {
      removeEventListener("monitor_changed", handleMonitorChange);
    };
  }, []);

  const handleReinstall = async () => {
    setInstalling(true);
    const success = await call<[], boolean>("reinstall_shaders");
    if (success) {
      setShaderInstalled(true);
    }
    setInstalling(false);
  };

  return (
    <>
      <ParallelPanelSection title="PLUGIN STATUS">
        <PlainButton
          label="Shader"
          value={shaderInstalled === null ? "Checking..." : shaderInstalled ? "Installed" : "Missing!"}
          modalTitle="Mura Correction Shaders"
          modalDesc="Shaders and mura texture are extracted into /home/deck/.local/share/gamescope/reshade"
        />
        {shaderInstalled === false && (
          <ButtonItem
            onClick={handleReinstall}
            layout="below"
            disabled={installing}
          > {installing ? "Installing..." : "Reinstall"}
          </ButtonItem>
        )}
        <PlainButton
          label="Current Display"
          value={
            externalMonitor === null
              ? "Detecting..."
              : externalMonitor
                ? "External Display"
                : "Internal Display"
          }
          onClick={() => { }}
        />
        <PlainButton
          label="Current Colorspace"
          value={displayMode || "Detecting..."}
          modalTitle="HDR Detection Compability"
          modalDesc="Current supported HDR detection is HDRscRGB and HDR10PQ. These colorspaces are used by most Steam games"
          description="Only limited HDR colorspace were supported - Click for more info"
        />
      </ParallelPanelSection>

      <ParallelPanelSection title="PLUGIN INFO">
        <PlainButton
          label="Plugin Codename"
          value={PLUGIN_NAME}
          modalTitle="Plugin Repo"
          modalDesc="For more info https://github.com/Moonveil-Kanata/MuraDeck"
        />
        <PlainButton
          label="Developer"
          value={PLUGIN_AUTHOR}
          onClick={() => { }}
        />
        <PlainButton
          label="Version"
          value={PLUGIN_VERSION + " Stable"}
          onClick={() => { }}
        />
      </ParallelPanelSection>
    </>
  );
}
