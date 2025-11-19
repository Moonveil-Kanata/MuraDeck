import {
  ButtonItem,
  PanelSectionRow,
  
} from "@decky/ui";
import { call, addEventListener, removeEventListener } from "@decky/api";

import { PlainButton } from "../components/styles/plainButton";
import { ParallelPanelSection } from "../components/styles/parallelPanelSec";
import { DisplayMode } from "../hooks/displayMode";
import { useState, useEffect } from "react";

import { FaExclamationCircle } from "react-icons/fa";

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
          onClick={() => { }}
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
          description="HDR Detection only for HDRscRGB and HDR10PQ, other than that it won't work as it needs special treatment for mura correction on every difference color profiles"
          value={displayMode || "Detecting..."}
          onClick={() => { }}
        />
      </ParallelPanelSection>

      <ParallelPanelSection title="PLUGIN INFO">
        <PlainButton
          label="Plugin Codename"
          value={PLUGIN_NAME}
          onClick={() => { }}
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
