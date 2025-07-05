import { call } from "@decky/api";

interface GameStateUpdate {
  unAppID: number;
  nInstanceID: number;
  bRunning: boolean;
}
let listenerRegistered = false;

export function registerGameStateListener() {
  if (listenerRegistered) return;
  listenerRegistered = true;

  SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications(
    (update: GameStateUpdate) => {
      console.log("[MuraDeck] GameStateUpdate", update);
      if (!update?.unAppID) return;

      call<[number, boolean], void>("on_game_state_update", update.unAppID, update.bRunning)
        .catch((err) => console.error("[MuraDeck] Failed to notify backend:", err));
    }
  );

  console.log("[MuraDeck] Game state listener registered.");
}
