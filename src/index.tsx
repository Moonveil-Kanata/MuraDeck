import {
  definePlugin,
  callable,
  routerHook
} from "@decky/api";
import { FaBraille } from "react-icons/fa";
import { Content } from "./components/content";

import { Menu } from "./pages/menu";
import { MENU_ROUTE } from "./router/routes";

import { isNewUser } from "./hooks/newUser";
import { registerResumeListener } from "./hooks/resumeListener";
import { registerBrightnessListener } from "./hooks/brightnessListener";

const getPluginEnabled = callable<[], boolean>("get_enabled");
const directEffect = callable<[], void>("direct_effect");

export default definePlugin(() => {
  console.log("[MuraDeck] Plugin initializing...");

  routerHook.addRoute(MENU_ROUTE, () => <Menu />);

  isNewUser();

  (async () => {
    const enabled = await getPluginEnabled();
    if (enabled) {
      console.log("[MuraDeck] Plugin is enabled on startup, applying effect instantly.");
      await directEffect();
    }
  })();

  const unregisterResume = registerResumeListener();
  const unregisterBrightness = registerBrightnessListener();

  return {
    name: "Mura Deck",
    titleView: <div>Mura Deck</div>,
    content: <Content />,
    icon: <FaBraille />,
    onDismount() {
      console.log("[MuraDeck] Unloading Mura Deck plugin");
      routerHook.removeRoute(MENU_ROUTE);
      unregisterBrightness?.();
      unregisterResume?.();
    },
  };
});
