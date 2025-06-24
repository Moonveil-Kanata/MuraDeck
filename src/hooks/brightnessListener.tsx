import { callable } from "@decky/api";

const getPluginEnabled = callable<[], boolean>("get_enabled");
const brightnessState = callable<[number], void>("brightness_state");

export function registerBrightnessListener(): () => void {
  try {
    const reg = window.SteamClient.System.Display.RegisterForBrightnessChanges(
      async ({ flBrightness }: { flBrightness: number }) => {
        const enabled = await getPluginEnabled();
        if (!enabled) return;

        const pct = Math.round(flBrightness * 100);
        console.log(`[MuraDeck] Brightness changed: ${pct}%`);
        await brightnessState(pct);
      }
    );

    return typeof reg === "function" ? reg : reg.unregister?.bind(reg) || (() => {});
  } catch (e) {
    console.error("[MuraDeck] Failed to register brightness listener", e);
    return () => {};
  }
}
