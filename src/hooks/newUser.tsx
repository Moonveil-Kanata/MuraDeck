import { callable } from "@decky/api";
import {
  Navigation
} from "@decky/ui";

const getHasSeenWelcome = callable<[], boolean>("get_has_seen_welcome");
const setHasSeenWelcome = callable<[boolean], void>("set_has_seen_welcome");

export async function isNewUser() {
  const hasSeen = await getHasSeenWelcome();
  if (!hasSeen) {
    console.log("[MuraDeck] Showing welcome screen");
    await setHasSeenWelcome(true);
    Navigation.CloseSideMenus();
    Navigation.Navigate("/mura-deck/menu/welcome");
  }
}
