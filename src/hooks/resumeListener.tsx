import { callable } from "@decky/api";

const getPluginEnabled = callable<[], boolean>("get_enabled");
const resumeFromSuspend = callable<[], void>("resume_from_suspend");

export function registerResumeListener(): () => void {
  const onResume = async () => {
    console.log("[MuraDeck] [Resume] Steam Deck resumed from suspend.");
    const enabled = await getPluginEnabled();
    if (enabled) {
      await resumeFromSuspend();
    }
  };

  try {
    const unsub = window.SteamClient?.System?.RegisterForOnResumeFromSuspend?.(onResume);
    if (typeof unsub === "function") {
      return unsub;
    }
  } catch (e) {
    console.warn("[MuraDeck] Failed to register resume listener", e);
  }

  return () => {};
}
