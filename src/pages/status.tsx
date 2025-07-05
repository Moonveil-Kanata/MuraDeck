import {
  ButtonItem
} from "@decky/ui";
import { call } from "@decky/api";

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

  useEffect(() => {
    const fetchShaderStatus = async () => {
      const installed = await call<[], boolean>("check_shader_status");
      setShaderInstalled(installed);
    };
    fetchShaderStatus();
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
          onClick={() => {}}
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
          label="Current Display status"
          value={displayMode || "Detecting..."}
          onClick={() => {}}
        />
      </ParallelPanelSection>

      <ParallelPanelSection title="PLUGIN INFO">
        <PlainButton
          label="Plugin Codename"
          value={PLUGIN_NAME}
          onClick={() => {}}
        />
        <PlainButton
          label="Developer"
          value={PLUGIN_AUTHOR}
          onClick={() => {}}
        />
        <PlainButton
          label="Version"
          value={PLUGIN_VERSION+" Beta Testflight"}
          onClick={() => {}}
        />
      </ParallelPanelSection>
    </>
  );
}