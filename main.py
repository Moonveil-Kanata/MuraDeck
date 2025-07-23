import os
import subprocess
import re
import decky
import asyncio
import shutil
import glob
import base64
from decky import emit

from settings import SettingsManager

settings = SettingsManager(
    name="settings",
    settings_directory=os.environ["DECKY_PLUGIN_SETTINGS_DIR"],
)
settings.read()

RESHADE_DIR = os.path.expanduser("~/.local/share/gamescope/reshade")
SHADER_DIR = os.path.join(RESHADE_DIR, "Shaders")
TEXTURE_DIR = os.path.join(RESHADE_DIR, "Textures")
MURA_TMP_DIR = "/tmp/mura"

PLUGIN_SHADERS_DIR = os.path.join(os.path.dirname(__file__), "shaders")

MURA_SHADER_FILES = [
    "CAS.fx",
    "MuraDeck_SDR.fx",
    "MuraDeck_HDR10PQ.fx",
    "MuraDeck_HDRscRGB.fx",
    "ReShade.fxh",
    "ReShadeUI.fxh",
]

MURA_TEXTURE_FILES = [
    "green.png",
    "red.png",
]

STEAM_ICON_PATH = os.path.expanduser("~/.steam/steam/appcache/librarycache")

LOG_DIR = os.path.expanduser("~/.steam/steam/logs")
LOG_LINUX = os.path.join(LOG_DIR, "console-linux.txt")
LOG_GAMEPROC = os.path.join(LOG_DIR, "gameprocess_log.txt")
LOG_DISPLAYMGR = os.path.join(LOG_DIR, "systemdisplaymanager.txt")

FX_DIR = os.path.expanduser("~/.local/share/gamescope/reshade/Shaders")
FX_CAS = "CAS.fx"
FX_SDR = "MuraDeck_SDR.fx"
FX_HDR10PQ = "MuraDeck_HDR10PQ.fx"
FX_HDRscRGB = "MuraDeck_HDRscRGB.fx"

STATIC_SDR = 0.0625
STATIC_HDR10PQ = (0.125, 2.5)
STATIC_HDRscRGB = 0.0125

BRIGHTNESS_TABLE_SDR = [
    (45, 0.0625),
    (40, 0.125),
    (0,  0.15),
]

BRIGHTNESS_TABLE_HDR10PQ = [
    (75, 0.125, 2.5),
    (70, 0.15,  3.0),
    (65, 0.175, 3.5),
    (60, 0.2,   4.0),
    (55, 0.25,  4.5),
    (50, 0.3,   4.75),
    (45, 0.3,   4.75),
    (40, 0.3,   4.75),
    (35, 0.35,  4.5),
    (30, 0.4,   4.0),
    (25, 0.45,  3.5),
    (20, 0.5,   3.0),
    (0,  0.525, 2.5),
]

BRIGHTNESS_TABLE_HDRscRGB = [
    (45, 0.0125),
    (40, 0.0150),
    (0,  0.0175),
]


class Plugin:
    def __init__(self):
        self._panel_not_sdc = False
        
        self.profile = "SDR"
        self.current_effect = FX_SDR
        self.current_appid: str | None = None

        self.last_map_scale: float | None = None
        self.last_fade_near: float | None = None

        self.current_brightness: int | None = None

        self._enabled = settings.getSetting("enabled", False)
        self._watch_task = None

        self._monitor_watch_enabled = settings.getSetting(
            "watch_external_monitor", True
        )
        self._is_external_display = False
        self._monitor_watch_task = None
        self._use_cas_only = False

        self._grain_enabled_sdr = settings.getSetting("grain_enabled_sdr", True)
        self._lgg_enabled_sdr = settings.getSetting("lgg_enabled_sdr", True)
        self._grain_enabled_hdr = settings.getSetting("grain_enabled_hdr", True)
        self._lgg_enabled_hdr = settings.getSetting("lgg_enabled_hdr", True)

        self._last_game_state: dict[int, bool] = {}
        self._app_profile_cache: dict[int, str] = {}
        self._last_focused_appid: int | None = None

        self._grain_enabled = self._grain_enabled_sdr
        self._lgg_enabled = self._lgg_enabled_sdr

        if self._is_external_display:
            self._current_cas: bool = settings.getSetting("cas_enabled_global_external", True)
            self._current_sharpness: float = settings.getSetting("sharpness_global_external", 0.0)
        else:
            self._current_cas: bool = settings.getSetting("cas_enabled_global_internal", False)
            self._current_sharpness: float = settings.getSetting("sharpness_global_internal", 0.0)

        self._brightness_enabled = settings.getSetting("brightness_enabled", True)

    async def _main(self):
        decky.logger.info("[MuraDeck] Started")
        if self._monitor_watch_enabled:
            self._monitor_watch_task = asyncio.create_task(
                self._ext_monitor_watcher()
            )
        if self._enabled:
            self._watch_task = asyncio.create_task(self._log_watcher())

    async def toggle_enabled(self, enable: bool):
        decky.logger.info(
            f"[MuraDeck] Toggling plugin to {'enabled' if enable else 'disabled'}"
        )
        settings.setSetting("enabled", enable)
        settings.commit()
        self._enabled = enable

        if enable:
            self.last_map_scale = None
            self.last_fade_near = None

            if self._watch_task is None or self._watch_task.done():
                self._watch_task = asyncio.create_task(self._log_watcher())
            await self._apply_current_profile()
        else:
            if self._watch_task and not self._watch_task.done():
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    decky.logger.info("[MuraDeck] Log watcher cancelled")
            await self._clear_effect()

    async def get_enabled(self) -> bool:
        return self._enabled

    async def get_display_mode(self) -> str:
        if self.profile == "SDR":
            return "SDR"
        elif self.profile == "HDR10PQ":
            return "HDR10 PQ"
        else:
            return "HDR scRGB"

    async def resume_from_suspend(self):
        if not self._enabled:
            decky.logger.info(
                "[MuraDeck] [Resume] Plugin disabled, skipping resume handler"
            )
            return
        decky.logger.info(
            "[MuraDeck] [Resume] Re-applying last known effect after suspend..."
        )
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def brightness_state(self, brightness: int):
        self.current_brightness = brightness
        if not self._enabled:
            return
        if not self._brightness_enabled:
            decky.logger.info("[MuraDeck] [Brightness=OFF]")
            await self._apply_static()
            return

        decky.logger.info(f"[MuraDeck] [Brightness] {brightness}% (Profile={self.profile})")
        if self.profile == "HDR10PQ":
            for thr, map_s, fade_n in BRIGHTNESS_TABLE_HDR10PQ:
                if brightness > thr:
                    if (
                        self.last_map_scale != map_s
                        or self.last_fade_near != fade_n
                    ):
                        decky.logger.info(
                            f"[MuraDeck] Updating HDR10PQ → Scale={map_s}, Fade={fade_n}"
                        )
                        await self._patch_fx(
                            FX_HDR10PQ, map_scale=map_s, fade_near=fade_n
                        )
                        await self._set_effect(FX_HDR10PQ)
                        self.last_map_scale = map_s
                        self.last_fade_near = fade_n
                    break
        elif self.profile == "HDRscRGB":
            for thr, map_s in BRIGHTNESS_TABLE_HDRscRGB:
                if brightness > thr:
                    if self.last_map_scale != map_s:
                        decky.logger.info(
                            f"[MuraDeck] Updating HDRscRGB → Scale={map_s}"
                        )
                        await self._patch_fx(FX_HDRscRGB, map_scale=map_s)
                        await self._set_effect(FX_HDRscRGB)
                        self.last_map_scale = map_s
                    break
        else:
            for thr, map_s in BRIGHTNESS_TABLE_SDR:
                if brightness > thr:
                    if self.last_map_scale != map_s:
                        decky.logger.info(f"[MuraDeck] Updating SDR → Scale={map_s}")
                        await self._patch_fx(FX_SDR, map_scale=map_s)
                        await self._set_effect(FX_SDR)
                        self.last_map_scale = map_s
                    break

    async def toggle_brightness(self, enable: bool):
        settings.setSetting("brightness_enabled", enable)
        settings.commit()
        self._brightness_enabled = enable
        decky.logger.info(
            f"[MuraDeck] Brightness State {'enabled' if enable else 'disabled'}"
        )
        self.last_map_scale = None
        self.last_fade_near = None
        if self._enabled and self.current_brightness is not None:
            await self.brightness_state(self.current_brightness)

    async def get_brightness_enabled(self) -> bool:
        return self._brightness_enabled
    
    async def get_steam_icon(self, appid: int, icon_hash: str) -> str | None:
        try:
            path = os.path.join(STEAM_ICON_PATH, str(appid), f"{icon_hash}.jpg")
            if not os.path.exists(path):
                return None
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                return encoded
        except Exception as e:
            print(f"[get_steam_icon] Error: {e}")
            return None
        
    async def on_focus_change(self):
        appid = await self.get_focused_appid()
        if appid is None or appid == self._last_focused_appid:
            return

        if self.current_appid is not None and self.profile is not None:
            try:
                prev_appid = int(self.current_appid)
                self._app_profile_cache[prev_appid] = self.profile
                decky.logger.info(f"[MuraDeck] Saved profile '{self.profile}' for AppID={prev_appid}")
            except Exception as e:
                decky.logger.warning(f"[MuraDeck] Save profile cache error: {e}")

        self._last_focused_appid = appid
        self.current_appid = str(appid)
        decky.logger.info(f"[MuraDeck] Focus changed to AppID={appid}")

        saved_profile = self._app_profile_cache.get(appid)
        if saved_profile:
            decky.logger.info(f"[MuraDeck] Restoring profile '{saved_profile}' for AppID={appid}")
            await self._set_profile(saved_profile)
            cas = await self.get_cas(appid)
            sharp = await self.get_sharpness(appid)
            self._current_cas = cas
            self._current_sharpness = sharp
            await self._patch_fx(self.current_effect)
            await self._set_effect(self.current_effect)
        else:
            decky.logger.info(f"[MuraDeck] No saved profile for AppID={appid}, using current")
        
    async def on_game_state_update(self, appid: int, running: bool):
        if not self._enabled and not self._use_cas_only:
            decky.logger.info("[MuraDeck] Plugin is disabled and not in CAS-only mode. Skipping game state update.")
            return
        # Fix redundant events from frontend
        last_state = self._last_game_state.get(appid)
        if last_state == running:
            return
        self._last_game_state[appid] = running

        if running:
            self.current_appid = str(appid)
            decky.logger.info(f"[MuraDeck] Game started: {appid}")

            wants_hdr = await self.check_gamescope_hdr()
            if not wants_hdr:
                decky.logger.info(f"[MuraDeck] Gamescope isn't HDR → SDR profile")
                await self._set_profile("SDR")

            sharp = await self.get_sharpness(appid)
            cas = await self.get_cas(appid)
            self._current_sharpness = sharp
            self._current_cas = cas

            if self._use_cas_only:
                decky.logger.info(f"[MuraDeck] [CAS-only] Applying sharp={sharp}, cas={cas}")
                await self._patch_fx(FX_CAS)
                await self._set_effect(FX_CAS)
            else:
                await self._apply_current_profile()
                await self._patch_fx(self.current_effect)
                await self._set_effect(self.current_effect)

        else:
            if appid in self._app_profile_cache:
                del self._app_profile_cache[appid]
                decky.logger.info(f"[MuraDeck] Cleared saved profile for closed AppID={appid}")
            decky.logger.info(f"[MuraDeck] Game closed: {appid}")
            self.current_appid = None
            self._current_sharpness = 0.0
            self._current_cas = False

            await self._set_profile("SDR")
            await self._patch_fx(self.current_effect)
            await self._set_effect(self.current_effect)

    async def _log_watcher(self):
        for p in (LOG_LINUX, LOG_GAMEPROC):
            if not os.path.exists(p):
                decky.logger.warning(f"[MuraDeck] Log not found: {p}")

        proc = await asyncio.create_subprocess_exec(
            "tail", "-F", LOG_LINUX, LOG_GAMEPROC,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout

        re_colorspace = re.compile(
            r"colorspace:.*(HDR10_ST2084|SRGB_NONLINEAR|SRGB_LINEAR)"
        )

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "ignore").rstrip()

            m = re_colorspace.search(text)
            if m:
                cs = m.group(1)
                if cs == "HDR10_ST2084":
                    await self._set_profile("HDR10PQ")
                elif cs == "SRGB_LINEAR":
                    await self._set_profile("HDRscRGB")
                else:
                    await self._set_profile("SDR")

    async def get_focused_appid(self):
        try:
            cmd = 'export DISPLAY=:0 && xprop -root GAMESCOPE_FOCUSED_APP'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                output = stdout.decode().strip()
                match = re.search(r"GAMESCOPE_FOCUSED_APP\(CARDINAL\) = (\d+)", output)
                if match:
                    appid = int(match.group(1))
                    decky.logger.info(f"[MuraDeck] Focused AppID: {appid}")
                    return appid
                else:
                    decky.logger.warning("[MuraDeck] GAMESCOPE_FOCUSED_APP not found in xprop output")
            else:
                decky.logger.error(f"[MuraDeck] Failed to run xprop: {stderr.decode().strip()}")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] get_focused_appid error: {e}")
        return None
    
    async def check_gamescope_hdr(self) -> bool:
        try:
            cmd = 'export DISPLAY=:0 && xprop -root GAMESCOPE_COLOR_APP_WANTS_HDR_FEEDBACK'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                output = stdout.decode().strip()
                match = re.search(r"GAMESCOPE_COLOR_APP_WANTS_HDR_FEEDBACK\(CARDINAL\) = (\d+)", output)
                if match:
                    value = int(match.group(1))
                    decky.logger.info(f"[MuraDeck] HDR Feedback Requested: {value}")
                    return value == 1
                else:
                    decky.logger.warning("[MuraDeck] HDR Feedback info not found in xprop output")
            else:
                decky.logger.error(f"[MuraDeck] xprop HDR check failed: {stderr.decode().strip()}")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] HDR feedback check error: {e}")
        return False

    async def _ext_monitor_watcher(self):
        if not os.path.exists(LOG_DISPLAYMGR):
            decky.logger.warning(
                "[MuraDeck] Log not found, failed to watch external monitor"
            )
            return
        decky.logger.info("[MuraDeck] Starting external monitor watcher...")
        proc = await asyncio.create_subprocess_exec(
            "tail", "-Fn0", LOG_DISPLAYMGR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        assert proc.stdout is not None
        pattern = re.compile(r"OnScreenChanged:\s+gamescope event external: (\d)")

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8").strip()
            match = pattern.search(decoded)
            if match:
                state = match.group(1)
                decky.logger.info(f"[Monitor Watcher] External = {state}")

                # Call focused appid
                await self.on_focus_change()
                if state == "1":
                    self._is_external_display = True
                    await emit("monitor_changed", True)
                    appid = await self.get_focused_appid()
                    if appid:
                        self._current_cas = await self.get_cas(appid)
                        self._current_sharpness = await self.get_sharpness(appid)
                        decky.logger.info(f"[Monitor] [External] Refreshed CAS={self._current_cas}, Sharp={self._current_sharpness}")

                    if self._monitor_watch_enabled:
                        decky.logger.info("[Monitor] External + Watch ON → CAS-only mode")
                        self._use_cas_only = True
                        if self._watch_task is None or self._watch_task.done():
                            self._watch_task = asyncio.create_task(self._log_watcher())
                        await self._patch_fx(FX_CAS)
                        await self._set_effect(FX_CAS)
                    else:
                        decky.logger.info("[Monitor] External + Watch OFF → normal MuraDeck")
                        self._use_cas_only = False
                        await self.toggle_enabled(True)
                elif state == "0":
                    self._is_external_display = False
                    await emit("monitor_changed", True)
                    self._use_cas_only = False

                    # Re-evaluate CAS and sharpness after monitor switch
                    appid = await self.get_focused_appid()
                    if appid:
                        self._current_cas = await self.get_cas(appid)
                        self._current_sharpness = await self.get_sharpness(appid)
                        decky.logger.info(f"[Monitor] [Internal] Refreshed CAS={self._current_cas}, Sharp={self._current_sharpness}")

                    if self._monitor_watch_enabled:
                        decky.logger.info("[Monitor] External disconnected → restoring MuraDeck")
                        if self._watch_task is None or self._watch_task.done():
                            self._watch_task = asyncio.create_task(self._log_watcher())
                        await self._apply_current_profile()
                        await self._patch_fx(self.current_effect)
                        await self._set_effect(self.current_effect)
                    else:
                        await self.toggle_enabled(True)


    async def is_external_display(self) -> bool:
        return self._is_external_display

    async def toggle_ext_monitor_watcher(self, enable: bool):
        settings.setSetting("watch_external_monitor", enable)
        settings.commit()
        self._monitor_watch_enabled = enable
        if enable:
            if self._monitor_watch_task is None or self._monitor_watch_task.done():
                self._monitor_watch_task = asyncio.create_task(self._ext_monitor_watcher())
        else:
            if self._monitor_watch_task and not self._monitor_watch_task.done():
                self._monitor_watch_task.cancel()
                try:
                    await self._monitor_watch_task
                except asyncio.CancelledError:
                    decky.logger.info("[MuraDeck] External monitor watcher cancelled")

    async def get_ext_monitor_watcher(self) -> bool:
        return self._monitor_watch_enabled

    async def _set_profile(self, profile: str):
        self.profile = profile
        if profile == "HDR10PQ":
            self.current_effect = FX_HDR10PQ
            self._grain_enabled = self._grain_enabled_hdr
            self._lgg_enabled = self._lgg_enabled_hdr
        elif profile == "HDRscRGB":
            self.current_effect = FX_HDRscRGB
            self._grain_enabled = self._grain_enabled_hdr
            self._lgg_enabled = self._lgg_enabled_hdr
        else:
            self.current_effect = FX_SDR
            self._grain_enabled = self._grain_enabled_sdr
            self._lgg_enabled = self._lgg_enabled_sdr

        decky.logger.info(f"[MuraDeck] Profile → {profile}, effect={self.current_effect}")

        if not self._brightness_enabled:
            await self._apply_static()
        elif self.current_brightness is not None:
            await self.brightness_state(self.current_brightness)
        else:
            await self._apply_effect(self.current_effect)

    async def _apply_current_profile(self):
        await self._set_profile(self.profile)

    async def _apply_static(self):
        if self.profile == "HDR10PQ":
            map_s, fade_n = STATIC_HDR10PQ
            decky.logger.info(f"[MuraDeck] Applying HDR10PQ static ({map_s},{fade_n})")
            await self._patch_fx(FX_HDR10PQ, map_s, fade_n)
            await self._set_effect(FX_HDR10PQ)
        elif self.profile == "HDRscRGB":
            decky.logger.info(f"[MuraDeck] Applying HDRscRGB static ({STATIC_HDRscRGB})")
            await self._patch_fx(FX_HDRscRGB, map_scale=STATIC_HDRscRGB)
            await self._set_effect(FX_HDRscRGB)
        else:
            decky.logger.info(f"[MuraDeck] Applying SDR static ({STATIC_SDR})")
            await self._patch_fx(FX_SDR, map_scale=STATIC_SDR)
            await self._set_effect(FX_SDR)

    async def _apply_effect(self, effect_file: str, map_scale=None, fade_near=None, hdr=None):
        await self._patch_fx(effect_file, map_scale=map_scale, fade_near=fade_near)
        await self._set_effect(effect_file)

    async def toggle_grain(self, enable: bool):
        if self.profile == "SDR":
            settings.setSetting("grain_enabled_sdr", enable)
            self._grain_enabled_sdr = enable
        else:
            settings.setSetting("grain_enabled_hdr", enable)
            self._grain_enabled_hdr = enable
        settings.commit()
        self._grain_enabled = enable
        decky.logger.info(f"[MuraDeck] Grain={'ON' if enable else 'OFF'} in {self.profile}")
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_grain(self) -> bool:
        return self._grain_enabled

    async def toggle_lgg(self, enable: bool):
        if self.profile == "SDR":
            settings.setSetting("lgg_enabled_sdr", enable)
            self._lgg_enabled_sdr = enable
        else:
            settings.setSetting("lgg_enabled_hdr", enable)
            self._lgg_enabled_hdr = enable
        settings.commit()
        self._lgg_enabled = enable
        decky.logger.info(f"[MuraDeck] LGG={'ON' if enable else 'OFF'} in {self.profile}")
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_lgg(self) -> bool:
        return self._lgg_enabled
    
    # Global Sharpness
    async def set_global_sharpness(self, value: float):
        key = (
            "sharpness_global_external"
            if self._is_external_display else
            "sharpness_global_internal"
        )
        settings.setSetting(key, value)
        settings.commit()

    async def get_global_sharpness(self) -> float:
        key = (
            "sharpness_global_external"
            if self._is_external_display else
            "sharpness_global_internal"
        )
        return settings.getSetting(key, 0.0)

    # Per-App Sharpness
    async def set_app_sharpness(self, appid: int, value: float):
        key = (
            f"sharpness_app_{appid}_external"
            if self._is_external_display else
            f"sharpness_app_{appid}_internal"
        )
        settings.setSetting(key, value)
        settings.commit()

    async def get_app_sharpness(self, appid: int) -> float | None:
        key = (
            f"sharpness_app_{appid}_external"
            if self._is_external_display else
            f"sharpness_app_{appid}_internal"
        )
        return settings.getSetting(key, None)
    
    # Per-App Enabled
    async def set_per_app_enabled(self, appid: int, enabled: bool):
        settings.setSetting(f"sharpness_perapp_enabled_{appid}", enabled)
        settings.commit()

    async def get_per_app_enabled(self, appid: int) -> bool:
        return settings.getSetting(f"sharpness_perapp_enabled_{appid}", False)
    
    # Global CAS toggle
    async def set_global_cas(self, value: bool):
        key = (
            "cas_enabled_global_external"
            if self._is_external_display else
            "cas_enabled_global_internal"
        )
        settings.setSetting(key, value)
        settings.commit()

    async def get_global_cas(self) -> bool:
        key = (
            "cas_enabled_global_external"
            if self._is_external_display else
            "cas_enabled_global_internal"
        )
        return settings.getSetting(key, False)
    
    # Per-App CAS toggle
    async def set_app_cas(self, appid: int, value: bool):
        key = (
            f"cas_enabled_app_{appid}_external"
            if self._is_external_display else
            f"cas_enabled_app_{appid}_internal"
        )
        settings.setSetting(key, value)
        settings.commit()

    async def get_app_cas(self, appid: int) -> bool | None:
        key = (
            f"cas_enabled_app_{appid}_external"
            if self._is_external_display else
            f"cas_enabled_app_{appid}_internal"
        )
        return settings.getSetting(key, None)

    async def set_cas_perapp_enabled(self, appid: int, enabled: bool):
        settings.setSetting(f"cas_perapp_enabled_{appid}", enabled)
        settings.commit()

    async def get_cas_perapp_enabled(self, appid: int) -> bool:
        return settings.getSetting(f"cas_perapp_enabled_{appid}", False)
    
    # CAS Activation
    async def set_cas(self, value: bool, appid: int | None, per_app: bool):
        if per_app and appid is not None:
            await self.set_app_cas(appid, value)
        else:
            await self.set_global_cas(value)

        self._current_cas = value

        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_cas(self, appid: int | None = None) -> bool:
        if appid is not None and await self.get_cas_perapp_enabled(appid):
            val = await self.get_app_cas(appid)
            if val is not None:
                return val
        return await self.get_global_cas()

    async def toggle_cas_perapp(self, appid: int, enable: bool):
        await self.set_cas_perapp_enabled(appid, enable)
        val = await self.get_cas(appid)

        self._current_cas = val

        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)
    
    # Sharpness
    async def set_sharpness(self, value: float, appid: int | None, per_app: bool):
        if per_app and appid is not None:
            await self.set_app_sharpness(appid, value)
        else:
            await self.set_global_sharpness(value)

        self._current_sharpness = value
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_sharpness(self, appid: int | None = None) -> float:
        if appid is not None and await self.get_per_app_enabled(appid):
            v = await self.get_app_sharpness(appid)
            if v is not None:
                return v
        return await self.get_global_sharpness()
    
    async def toggle_sharpness_perapp(self, appid: int, enable: bool):
        await self.set_per_app_enabled(appid, enable)

        value = await self.get_sharpness(appid)

        self._current_sharpness = value
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_sharpness_perapp_enabled(self, appid: int) -> bool:
        return await self.get_per_app_enabled(appid)

    async def _patch_fx(
            self, fx_name: str, map_scale: float | None = None,
            fade_near: float | None = None):
        if self._use_cas_only:
            fx_name = FX_CAS
        
        path = os.path.join(FX_DIR, fx_name)
        if not os.path.isfile(path):
            decky.logger.error(f"[MuraDeck] FX file not found: {path}")
            return

        is_sdr = (fx_name == FX_SDR)
        is_hdrscrgb = (fx_name == FX_HDRscRGB)
        
        if is_hdrscrgb:
            grain_value = 0.1 if self._grain_enabled else 0.0
            lgg_lift_value = 0.99992 if self._lgg_enabled else 1.0
            lgg_gamma_value = 0.75 if self._lgg_enabled else 1.0
        elif is_sdr:
            grain_value = 0.01 if self._grain_enabled else 0.0
            lgg_lift_value = 0.95 if self._lgg_enabled else 1.0
            lgg_gamma_value = 0.98 if self._lgg_enabled else 1.0
        else:
            if self._lgg_enabled:
                lgg_lift_value = "float3(1.0, 0.99, 1.0)"
                lgg_gamma_value = 1.0
            else:
                lgg_lift_value = 1.0
                lgg_gamma_value = 1.0
            grain_value = 0.01 if self._grain_enabled else 0.0

        cas_enabled = 1.0 if self._current_cas else 0.0
        sharpness = self._current_sharpness

        with open(path, "r") as f:
            lines = f.readlines()

        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # CAS toggle
            if cas_enabled is not None and "uniform float CAS_Enabled" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float CAS_Enabled <\n',
                    '\tui_label = "Turn On/Off CAS";\n',
                    '\tui_tooltip = "0 := disable, to 1 := enable.";\n',
                    '\tui_min = 0.0; ui_max = 1.0;\n',
                    '\tui_step = 1.0;\n',
                    f'> = {cas_enabled};\n'
                ])
                continue

            # patch Sharpness
            if sharpness is not None and "uniform float Sharpness" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float Sharpness <\n',
                    '\tui_type = "drag";\n',
                    '\tui_label = "Sharpening strength";\n',
                    '\tui_tooltip = "0 := no sharpening, to 1 := full sharpening.";\n',
                    '\tui_min = 0.0; ui_max = 1.0;\n',
                    f'> = {sharpness};\n'
                ])
                continue

            # patch MuraMapScale
            if map_scale is not None and "uniform float MuraMapScale" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float MuraMapScale < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.0; ui_max = 5;\n',
                    '\tui_label = "Mura Correction Strength";\n',
                    '\tui_tooltip = "Controls how aggressive mura map.";\n',
                    f'> = {map_scale};\n'
                ])
                continue

            # patch MuraFadeNearWhite
            if fade_near is not None and "uniform float MuraFadeNearWhite" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float MuraFadeNearWhite < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.1; ui_max = 20;\n',
                    '\tui_label = "Mura Fade Near White";\n',
                    '\tui_tooltip = "Controls how fast mura fix fades out to bright pixel.";\n',
                    f'> = {fade_near};\n'
                ])
                continue

            # patch grain intensity
            if "uniform float Intensity" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float Intensity < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.0; ui_max = 1.0;\n',
                    '\tui_label = "Grain Intensity";\n',
                    '\tui_tooltip = "How visible the grain is.";\n',
                    f'> = {grain_value};\n'
                ])
                continue

            # patch RGB Lift/Gamma
            if "uniform float3 RGB_Lift" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float3 RGB_Lift < __UNIFORM_SLIDER_FLOAT3\n',
                    '\tui_min = 0.0; ui_max = 2.0;\n',
                    '\tui_label = "RGB Lift";\n',
                    '\tui_tooltip = "Adjust shadows.";\n',
                    f'> = {lgg_lift_value};\n'
                ])
                continue

            if "uniform float3 RGB_Gamma" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float3 RGB_Gamma < __UNIFORM_SLIDER_FLOAT3\n',
                    '\tui_min = 0.1; ui_max = 3.0;\n',
                    '\tui_label = "RGB Gamma";\n',
                    '\tui_tooltip = "Adjust midtones.";\n',
                    f'> = {lgg_gamma_value};\n'
                ])
                continue

            out.append(line)
            i += 1

        with open(path, "w") as f:
            f.writelines(out)

        temp_path = path.replace(".fx", "_temp.fx")
        try:
            shutil.copy(path, temp_path)
            decky.logger.info(f"[MuraDeck] Temp effect: {temp_path}")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Temp effect failed: {e}")

        decky.logger.info(
            f"[MuraDeck] FX patched: {fx_name} → Grain={grain_value}, "
            f"LGG Lift/Gamma=({lgg_lift_value},{lgg_gamma_value})"
            f"CAS={cas_enabled}, Sharpness={sharpness}"
        )

    async def _clear_effect(self):
        cmd = (
            'export DISPLAY=:1 && '
            'xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u '
            '-set GAMESCOPE_RESHADE_EFFECT None'
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()
        if proc.returncode == 0:
            decky.logger.info("[MuraDeck] Cleared ReShade effect")
        else:
            decky.logger.error(f"[MuraDeck] Clear effect failed: {err.decode().strip()}")

    async def direct_effect(self):
        decky.logger.info("[MuraDeck] DirectFX apply")
        effect_name = self.current_effect or FX_SDR
        cmd = (
            f'export DISPLAY=:1 && '
            f'xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u '
            f'-set GAMESCOPE_RESHADE_EFFECT {effect_name}'
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()
        if proc.returncode == 0:
            decky.logger.info(f"[MuraDeck] Effect set to {effect_name}")
        else:
            decky.logger.error(f"[MuraDeck] DirectFX error: {err.decode().strip()}")

    async def _set_effect(self, effect_name: str):
        if self._use_cas_only:
            effect_name = FX_CAS

        temp = effect_name.replace(".fx", "_temp.fx")
        cmd = (
            f'export DISPLAY=:1 && '
            f'xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u '
            f'-set GAMESCOPE_RESHADE_EFFECT {temp} && '
            'sleep 0.5 && '
            f'xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u '
            f'-set GAMESCOPE_RESHADE_EFFECT {effect_name}'
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()
        if proc.returncode == 0:
            decky.logger.info(f"[MuraDeck] Set effect {effect_name}")
        else:
            decky.logger.error(f"[MuraDeck] Set effect failed: {err.decode().strip()}")

    async def check_shader_status(self) -> bool:
        shaders_exist = all(
            os.path.exists(os.path.join(SHADER_DIR, f))
            for f in MURA_SHADER_FILES
        )
        textures_exist = all(
            os.path.exists(os.path.join(TEXTURE_DIR, f))
            for f in MURA_TEXTURE_FILES
        )
        return shaders_exist and textures_exist

    async def reinstall_shaders(self) -> bool:
        try:
            await self._migration()
            return True
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Reinstall failed: {e}")
            return False

    async def get_has_seen_welcome(self) -> bool:
        return settings.getSetting("has_seen_welcome", False)

    async def set_has_seen_welcome(self, seen: bool):
        settings.setSetting("has_seen_welcome", seen)
        settings.commit()

    async def _unload(self):
        decky.logger.info("[MuraDeck] Unloading...")

    async def _uninstall(self):
        settings.setSetting("has_seen_welcome", False)
        settings.commit()
        decky.logger.info("[MuraDeck] Reset welcome flag on uninstall")

        # Remove shaders
        all_shaders = MURA_SHADER_FILES + [
            "MuraDeck_SDR_temp.fx",
            "MuraDeck_HDR10PQ_temp.fx",
            "MuraDeck_HDRscRGB_temp.fx",
        ]
        for fn in all_shaders:
            try:
                os.remove(os.path.join(SHADER_DIR, fn))
                decky.logger.info(f"[MuraDeck] Deleted shader: {fn}")
            except FileNotFoundError:
                pass
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Delete shader {fn} error: {e}")

        # Remove textures
        for fn in MURA_TEXTURE_FILES:
            try:
                os.remove(os.path.join(TEXTURE_DIR, fn))
                decky.logger.info(f"[MuraDeck] Deleted texture: {fn}")
            except FileNotFoundError:
                pass
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Delete texture {fn} error: {e}")

        try:
            t = asyncio.create_task(self._clear_effect())
            await asyncio.wait_for(t, timeout=2.0)
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Clear effect failed: {e}")

    async def _migration(self):
        decky.logger.info("[MuraDeck] Migration step")

        ena = settings.getSetting("enabled", None)
        if ena is None:
            decky.logger.info("[MuraDeck] First-time: disabling plugin")
            settings.setSetting("enabled", False)
            settings.commit()
            self._enabled = False
        else:
            self._enabled = ena

        os.makedirs(SHADER_DIR, exist_ok=True)
        os.makedirs(TEXTURE_DIR, exist_ok=True)

        # Mura map extractor
        decky.logger.info("[MuraDeck] Installing shaders...")
        for cmd in ["galileo-mura-extractor", "galileo-mura-setup"]:
            try:
                env = os.environ.copy()
                env["DISPLAY"] = ":0"
                proc = await asyncio.create_subprocess_exec(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                out, err = await proc.communicate()
                if proc.returncode == 0:
                    decky.logger.info(f"[MuraDeck] {cmd} OK")
                else:
                    decky.logger.error(f"[MuraDeck] {cmd} FAILED: {err.decode()}")

                # If not SDC / BOE Detected
                if cmd == "galileo-mura-extractor":
                    stdout_str = out.decode().lower()
                    if "not using mura correction" in stdout_str and "not sdc" in stdout_str:
                        self._panel_not_sdc = True
                        decky.logger.warning("[MuraDeck] Panel is NOT SDC")

            except Exception as e:
                decky.logger.error(f"[MuraDeck] Run {cmd} error: {e}")
                    
        # Copy from /tmp/mura
        try:
            green_tmp = glob.glob(os.path.join("/tmp/mura", "*green.png"))
            red_tmp = glob.glob(os.path.join("/tmp/mura", "*red.png"))
            if green_tmp:
                shutil.copy(green_tmp[0], os.path.join(TEXTURE_DIR, "green.png"))
                decky.logger.info("[MuraDeck] Copied green.png from /tmp/mura")
            if red_tmp:
                shutil.copy(red_tmp[0], os.path.join(TEXTURE_DIR, "red.png"))
                decky.logger.info("[MuraDeck] Copied red.png from /tmp/mura")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Failed to copy from /tmp/mura: {e}")

        # Copy from ~/.config/gamescope/mura/{id}
        try:
            mura_config_dir = os.path.expanduser("~/.config/gamescope/mura")
            candidate_dirs = glob.glob(os.path.join(mura_config_dir, "*"))
            found = False

            for candidate in candidate_dirs:
                green = glob.glob(os.path.join(candidate, "*green.png"))
                red = glob.glob(os.path.join(candidate, "*red.png"))
                if green and red:
                    shutil.copy(green[0], os.path.join(TEXTURE_DIR, "green.png"))
                    shutil.copy(red[0], os.path.join(TEXTURE_DIR, "red.png"))
                    decky.logger.info(f"[MuraDeck] Copied green.png from {candidate}")
                    decky.logger.info(f"[MuraDeck] Copied red.png from {candidate}")
                    found = True
                    break

            if not found:
                decky.logger.warning("[MuraDeck] No valid fallback texture found in ~/.config/gamescope/mura")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Failed to fallback copy from ~/.config/gamescope/mura: {e}")

        # Install all shaders
        for fn in MURA_SHADER_FILES:
            src = os.path.join(PLUGIN_SHADERS_DIR, fn)
            dst = os.path.join(SHADER_DIR, fn)
            try:
                shutil.copy(src, dst)
                os.chmod(dst, 0o644)
                decky.logger.info(f"[MuraDeck] Installed shader {fn}")
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Install shader {fn} error: {e}")

        # Welcome flag
        seen = settings.getSetting("has_seen_welcome", None)
        if seen is None:
            decky.logger.info("[MuraDeck] First-time: mark welcome")
            settings.setSetting("has_seen_welcome", False)
            settings.commit()