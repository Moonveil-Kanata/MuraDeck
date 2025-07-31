import {
  ToggleField,
  PanelSection,
  PanelSectionRow,
  SliderField
} from "@decky/ui";
import { call, addEventListener, removeEventListener } from "@decky/api";
import { useState, useEffect, useCallback } from "react";
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

  const [currentApp, setCurrentApp] = useState<{
    appid: number;
    name: string;
    icon?: string;
  } | null>(null);

  const [sharpness, setSharpness] = useState(0);
  const [casEnabled, setCasEnabled] = useState(false);
  const [perAppCas, setPerAppCas] = useState(false);
  const [perAppSharpness, setPerAppSharpness] = useState(false);

  const [externalMonitor, setExternalMonitor] = useState<boolean | null>(null);

  const [isTogglingEnabled, setIsTogglingEnabled] = useState(false);
  const [isTogglingBrightness, setIsTogglingBrightness] = useState(false);
  const [isTogglingGrain, setIsTogglingGrain] = useState(false);
  const [isTogglingLGG, setIsTogglingLGG] = useState(false);

  const displayMode = DisplayMode();

  // Delay toggle helper
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
      await new Promise((r) => setTimeout(r, 500));
    } catch (e) {
      console.error(`[${apiFn}] failed`, e);
    }
    setLoading(false);
  };

  // Refresh all related state from backend
  const refreshAll = useCallback(async () => {
    // external monitor
    try {
      const ext = await call<[], boolean>("is_external_display");
      setExternalMonitor(ext);
    } catch { }

    // global toggles + welcome + shader status
    try {
      const [en, mon, bright, seen, ok] = await Promise.all([
        call<[], boolean>("get_enabled"),
        call<[], boolean>("get_ext_monitor_watcher"),
        call<[], boolean>("get_brightness_enabled"),
        call<[], boolean>("get_has_seen_welcome"),
        call<[], boolean>("check_shader_status"),
      ]);
      setEnabled(en);
      setMonitorWatch(mon);
      setBrightnessEnabled(bright);
      setWelcomePassed(seen);
      setShaderReady(ok);
    } catch { }

    // grain & LGG
    if (displayMode !== null) {
      try {
        const [g, l] = await Promise.all([
          call<[], boolean>("get_grain"),
          call<[], boolean>("get_lgg"),
        ]);
        setGrain(g);
        setLGG(l);
      } catch { }
    }

    // per-app or global sharpness & CAS
    if (currentApp?.appid) {
      try {
        const [sEn, sVal, cEn, cVal] = await Promise.all([
          call<[number], boolean>("get_sharpness_perapp_enabled", currentApp.appid),
          call<[number], number>("get_sharpness", currentApp.appid),
          call<[number], boolean>("get_cas_perapp_enabled", currentApp.appid),
          call<[number], boolean>("get_cas", currentApp.appid),
        ]);
        setPerAppSharpness(sEn);
        setSharpness(sVal);
        setPerAppCas(cEn);
        setCasEnabled(cVal);
      } catch { }
    } else {
      try {
        const [sVal, cVal] = await Promise.all([
          call<[], number>("get_sharpness"),
          call<[], boolean>("get_cas"),
        ]);
        setSharpness(sVal);
        setCasEnabled(cVal);
      } catch { }
    }
  }, [currentApp?.appid, displayMode]);

  // Init + backend→frontend events
  useEffect(() => {
    refreshAll();

    const onMonitor = (_: any, isExt: boolean) => {
      setExternalMonitor(isExt);
      refreshAll();
    };
    const onAppProf = () => {
      refreshAll();
    };

    addEventListener("monitor_changed", onMonitor);
    addEventListener("app_profile_applied", onAppProf);

    return () => {
      removeEventListener("monitor_changed", onMonitor);
      removeEventListener("app_profile_applied", onAppProf);
    };
  }, [refreshAll]);

  // Detect running Steam game
  useEffect(() => {
    const loadAppInfo = async () => {
      try {
        const running = (window as any).SteamUIStore?.RunningApps;
        if (Array.isArray(running) && running.length > 0) {
          const app = running[0];
          let iconUrl: string | undefined;

          if (app.icon_data) {
            const fmt = app.icon_data_format ?? "png";
            iconUrl = `data:image/${fmt};base64,${app.icon_data}`;
          } else if (app.icon_hash) {
            const b64 = await call<[number, string], string | null>(
              "get_steam_icon",
              app.appid,
              app.icon_hash
            );
            if (b64) iconUrl = `data:image/jpeg;base64,${b64}`;
          }

          setCurrentApp({
            appid: app.appid,
            name: app.display_name ?? "Unknown",
            icon: iconUrl,
          });
        } else {
          setCurrentApp(null);
        }
      } catch (e) {
        console.error("Failed to load SteamUIStore.RunningApps", e);
      }
    };
    loadAppInfo();
  }, []);

  // When currentApp changes, re-fetch per-app fields only
  useEffect(() => {
    if (currentApp?.appid) {
      refreshAll();
    }
  }, [currentApp, refreshAll]);

  return (
    <>
      <PanelSection title="Gamescope">
        <EffectInfo effectKey="mura">
          <PanelSectionRow>
            <ToggleField
              disabled={
                !welcomePassed || shaderReady === false || isTogglingEnabled
              }
              label={Desc.mura.title}
              checked={enabled}
              onChange={(v) =>
                delayToggle(
                  "toggle_enabled",
                  v,
                  setEnabled,
                  setIsTogglingEnabled
                )
              }
            />
          </PanelSectionRow>
        </EffectInfo>

        <EffectInfo effectKey="monitor">
          <PanelSectionRow>
            <ToggleField
              disabled={!welcomePassed || shaderReady === false}
              label={Desc.monitor.title}
              checked={monitorWatch}
              onChange={async (v) => {
                setMonitorWatch(v);
                await call<[boolean], void>("toggle_ext_monitor_watcher", v);
              }}
            />
          </PanelSectionRow>
        </EffectInfo>
      </PanelSection>

      <PanelSection title="Mura Settings">
        <EffectInfo effectKey="brightness">
          <PanelSectionRow>
            <ToggleField
              disabled={
                !welcomePassed ||
                shaderReady === false ||
                isTogglingBrightness
              }
              label={Desc.brightness.title}
              description={isTogglingBrightness ? Desc.loading.title : ""}
              checked={brightnessEnabled}
              onChange={(v) =>
                delayToggle(
                  "toggle_brightness",
                  v,
                  setBrightnessEnabled,
                  setIsTogglingBrightness
                )
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
              description={isTogglingGrain ? `Saving to ${displayMode}...` : ""}
              checked={grain}
              onChange={(v) =>
                delayToggle("toggle_grain", v, setGrain, setIsTogglingGrain)
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
              description={isTogglingLGG ? `Saving to ${displayMode}...` : ""}
              checked={lgg}
              onChange={(v) =>
                delayToggle("toggle_lgg", v, setLGG, setIsTogglingLGG)
              }
              icon={<Desc.lgg.icon />}
            />
          </PanelSectionRow>
        </EffectInfo>
      </PanelSection>

      <PanelSection title="AMD Fidelity FX">
        <PanelSectionRow>
          <ToggleField
            label="Per‑game CAS"
            checked={perAppSharpness || perAppCas}
            disabled={!currentApp}
            onChange={async (v) => {
              if (!currentApp) return;
              await Promise.all([
                call<[number, boolean], void>(
                  "toggle_sharpness_perapp",
                  currentApp.appid,
                  v
                ),
                call<[number, boolean], void>(
                  "toggle_cas_perapp",
                  currentApp.appid,
                  v
                ),
              ]);
              refreshAll();
            }}
            description={
              (perAppSharpness || perAppCas) && currentApp ? (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      color: "rgba(255,255,255,0.6)",
                    }}
                  >
                    {currentApp.icon && (
                      <img
                        src={currentApp.icon}
                        alt=""
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: 3,
                        }}
                      />
                    )}
                    <span>{currentApp.name}</span>
                  </div>
                </div>
              ) : undefined
            }
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Enable AMD CAS"
            checked={casEnabled}
            disabled={!currentApp}
            onChange={async (v) => {
              if (!currentApp) return;
              setCasEnabled(v);
              await call<[boolean, number | null, boolean], void>(
                "set_cas",
                v,
                currentApp.appid,
                perAppCas
              );
            }}
            description={
              casEnabled && externalMonitor !== null ? (
                <div
                  style={{
                    fontSize: 13,
                    color: "rgba(255,255,255,0.5)",
                  }}
                >
                  Current Profile for:{" "}
                  {externalMonitor ? "External Monitor" : "Internal Display"}
                </div>
              ) : undefined
            }
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <SliderField
            label="Sharpness"
            min={0}
            max={1}
            step={0.25}
            notchCount={5}
            notchLabels={[
              { notchIndex: 0, label: "Light" },
              { notchIndex: 1, label: "Fair" },
              { notchIndex: 2, label: "Med" },
              { notchIndex: 3, label: "High" },
              { notchIndex: 4, label: "Firm" },
            ]}
            value={sharpness}
            showValue
            disabled={!currentApp}
            onChange={async (v: number) => {
              if (!currentApp) return;
              setSharpness(v);
              await call<[number, number | null, boolean], void>(
                "set_sharpness",
                v,
                currentApp.appid,
                perAppSharpness
              );
            }}
          />
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}
