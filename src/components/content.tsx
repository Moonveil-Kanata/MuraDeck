import {
  ToggleField,
  PanelSection,
  PanelSectionRow
} from "@decky/ui";
import { call } from "@decky/api";
import { useState, useEffect } from "react";
import { FaInfoCircle } from "react-icons/fa";

import { STATUS_ROUTE } from "../router/routes";
import { EffectInfo } from "./styles/effectInfo";
import { StatusButton } from "./styles/statusButton";

import { DisplayMode } from "../hooks/displayMode";
import { Desc } from "./defines/descriptor";

export function Content() {
  const [welcomePassed, setWelcomePassed] = useState(false);

  const [enabled, setEnabled] = useState(true);
  const [brightnessEnabled, setBrightnessEnabled] = useState(true);
  const [grain, setGrain] = useState(false);
  const [lgg, setLGG] = useState(false);
  const [monitorWatch, setMonitorWatch] = useState(true);
  const [shaderReady, setShaderReady] = useState<boolean | null>(null);

  const [isTogglingEnabled, setIsTogglingEnabled] = useState(false);
  const [isTogglingBrightness, setIsTogglingBrightness] = useState(false);
  const [isTogglingGrain, setIsTogglingGrain] = useState(false);
  const [isTogglingLGG, setIsTogglingLGG] = useState(false);

  const displayMode = DisplayMode();

  useEffect(() => {
    const init = async () => {
      try {
        const [en, mon, bright, seen] = await Promise.all([
          call<[], boolean>("get_enabled"),
          call<[], boolean>("get_ext_monitor_watcher"),
          call<[], boolean>("get_brightness_enabled"),
          call<[], boolean>("get_has_seen_welcome")
        ]);
        setEnabled(en);
        setMonitorWatch(mon);
        setBrightnessEnabled(bright);
        setWelcomePassed(seen);
      } catch (e) {
        console.error("Failed to fetch:", e);
      }

      try {
        if (displayMode !== null) {
          const g = await call<[], boolean>("get_grain");
          const l = await call<[], boolean>("get_lgg");
          setGrain(g);
          setLGG(l);
        }
      } catch (e) {
        console.error("Failed to fetch grain/lgg:", e);
      }

      try {
        const ok = await call<[], boolean>("check_shader_status");
        setShaderReady(ok);
      } catch (e) {
        console.error("Failed to check shader status:", e);
        setShaderReady(false);
      }
    };

    init();
  }, [displayMode]);

  const delayToggle = async (
    apiFn: string,
    value: boolean,
    setState: (v: boolean) => void,
    setLoading: (v: boolean) => void
  ) => {
    setLoading(true);
    setState(value);
    try {
      await call<[boolean], void>(apiFn, value);
      await new Promise(res => setTimeout(res, 500));
    } catch (e) {
      console.error(`[${apiFn}] failed`, e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PanelSection title="Gamescope">
        <EffectInfo effectKey="mura">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false || isTogglingEnabled}
              label={Desc.mura.title}
              checked={enabled}
              onChange={val =>
                delayToggle("toggle_enabled", val, setEnabled, setIsTogglingEnabled)
              }
            />
          </PanelSectionRow>
        </EffectInfo>
      </PanelSection>

      <PanelSection title="Configuration">
        <EffectInfo effectKey="monitor">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false}
              label={Desc.monitor.title}
              checked={monitorWatch}
              onChange={async val => {
                setMonitorWatch(val);
                await call<[boolean], void>("toggle_ext_monitor_watcher", val);
              }}
              icon={<Desc.monitor.icon />}
            />
          </PanelSectionRow>
        </EffectInfo>

        <EffectInfo effectKey="brightness">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false || isTogglingBrightness}
              label={Desc.brightness.title}
              description={isTogglingBrightness ? Desc.loading.title : ""}
              checked={brightnessEnabled}
              onChange={val =>
                delayToggle("toggle_brightness", val, setBrightnessEnabled, setIsTogglingBrightness)
              }
              icon={<Desc.brightness.icon />}
            />
          </PanelSectionRow>
        </EffectInfo>

        <StatusButton
          label="Status"
          description={
            shaderReady === false
              ? "Reinstalling required!"
              : displayMode
                ? `Current Profile: ${displayMode}`
                : Desc.loading.desc
          }
          icon={<FaInfoCircle />}
          route={STATUS_ROUTE}
          disabled={!welcomePassed || shaderReady === false}
        />

        <EffectInfo effectKey="grain">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false || isTogglingGrain}
              label={Desc.grain.title}
              description={isTogglingGrain ? "Saving to "+displayMode+"..." : ""}
              checked={grain}
              onChange={val =>
                delayToggle("toggle_grain", val, setGrain, setIsTogglingGrain)
              }
              icon={<Desc.grain.icon />}
            />
          </PanelSectionRow>
        </EffectInfo>

        <EffectInfo effectKey="lgg">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false || isTogglingLGG}
              label={Desc.lgg.title}
              description={isTogglingLGG ? "Saving to "+displayMode+"..." : ""}
              checked={lgg}
              onChange={val =>
                delayToggle("toggle_lgg", val, setLGG, setIsTogglingLGG)
              }
              icon={<Desc.lgg.icon />}
            />
          </PanelSectionRow>
        </EffectInfo>
      </PanelSection>
    </>
  );
}
