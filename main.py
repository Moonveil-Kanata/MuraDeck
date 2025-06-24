import os
import subprocess
import re
import decky
import asyncio
import shutil
import glob

from settings import SettingsManager

settings = SettingsManager(name="settings", settings_directory=os.environ["DECKY_PLUGIN_SETTINGS_DIR"])
settings.read()

RESHADE_DIR = os.path.expanduser("~/.local/share/gamescope/reshade")
SHADER_DIR = os.path.join(RESHADE_DIR, "Shaders")
TEXTURE_DIR = os.path.join(RESHADE_DIR, "Textures")
MURA_TMP_DIR = "/tmp/mura"

PLUGIN_SHADERS_DIR = os.path.join(os.path.dirname(__file__), "shaders")

MURA_SHADER_FILES = [
    "MuraDeck_SDR.fx",
    "MuraDeck_HDR.fx",
    "ReShade.fxh",
    "ReShadeUI.fxh",
]

MURA_TEXTURE_FILES = [
    "green.png",
    "red.png",
]

LOG_DIR = os.path.expanduser("~/.steam/steam/logs")
LOG_CONSOLE = os.path.join(LOG_DIR, "console-linux.txt")
LOG_GAMEPROC = os.path.join(LOG_DIR, "gameprocess_log.txt")
LOG_DISPLAYMGR = os.path.join(LOG_DIR, "systemdisplaymanager.txt")

FX_DIR = os.path.expanduser("~/.local/share/gamescope/reshade/Shaders")
FX_HDR = "MuraDeck_HDR.fx"
FX_SDR = "MuraDeck_SDR.fx"

STATIC_HDR = (0.125, 2.5)
STATIC_SDR = 0.0625

BRIGHTNESS_TABLE_HDR = [
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

BRIGHTNESS_TABLE_SDR = [
    (45, 0.0625),
    (40, 0.125),
    (0,  0.15),
]

class Plugin:
    def __init__(self):
        self.is_hdr = False

        self.current_effect = FX_SDR
        self.current_appid: str | None = None

        self.last_map_scale: float | None = None
        self.last_fade_near: float | None = None

        self.current_brightness: int | None = None
        
        self._enabled = settings.getSetting("enabled", False)
        self._watch_task = None

        self._monitor_watch_enabled = settings.getSetting("watch_external_monitor", True)
        self._monitor_watch_task = None

        self._grain_enabled_hdr = settings.getSetting("grain_enabled_hdr", True)
        self._grain_enabled_sdr = settings.getSetting("grain_enabled_sdr", True)
        self._lgg_enabled_hdr = settings.getSetting("lgg_enabled_hdr", True)
        self._lgg_enabled_sdr = settings.getSetting("lgg_enabled_sdr", True)
        
        self._grain_enabled = self._grain_enabled_sdr
        self._lgg_enabled = self._lgg_enabled_sdr

        self._brightness_enabled = settings.getSetting("brightness_enabled", True)

    async def _main(self):
        decky.logger.info("[MuraDeck] Started")

        if self._monitor_watch_enabled:
            self._monitor_watch_task = asyncio.create_task(self._ext_monitor_watcher())

        if self._enabled:
            self._watch_task = asyncio.create_task(self._log_watcher())

    async def toggle_enabled(self, enable: bool):
        decky.logger.info(f"[MuraDeck] Toggling plugin to {'enabled' if enable else 'disabled'}")
        settings.setSetting("enabled", enable)
        settings.commit()
        self._enabled = enable

        if enable:
            if self._watch_task is None or self._watch_task.done():
                self._watch_task = asyncio.create_task(self._log_watcher())
            if self.is_hdr:
                await self._apply_effect(FX_HDR, hdr=True)
            else:
                await self._apply_effect(FX_SDR, hdr=False)
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
        return "HDR" if self.is_hdr else "SDR"

    async def resume_from_suspend(self):
        if not self._enabled:
            decky.logger.info("[MuraDeck] [Resume] Plugin disabled, skipping resume handler")
            return

        decky.logger.info("[MuraDeck] [Resume] Re-applying last known effect after suspend...")
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def brightness_state(self, brightness: int):
        self.current_brightness = brightness

        if not self._enabled:
            return
        if not self._brightness_enabled:
            if self.is_hdr:
                map_s, fade_n = STATIC_HDR
                decky.logger.info(f"[MuraDeck] [Brightness=OFF] Applying static HDR ({map_s},{fade_n})")
                await self._patch_fx(FX_HDR, map_s, fade_n)
                await self._set_effect(FX_HDR)
            else:
                decky.logger.info(f"[MuraDeck] [Brightness=OFF] Applying static SDR ({STATIC_SDR})")
                await self._patch_fx(FX_SDR, map_scale=STATIC_SDR)
                await self._set_effect(FX_SDR)
            return

        decky.logger.info(f"[MuraDeck] [Brightness] {brightness}% (HDR={self.is_hdr})")
        if self.is_hdr:
            for thr, map_scale, fade_near in BRIGHTNESS_TABLE_HDR:
                if brightness > thr:
                    if (self.last_map_scale != map_scale) or (self.last_fade_near != fade_near):
                        decky.logger.info(f"[MuraDeck] [Brightness] Updating HDR → Scale={map_scale}, Fade={fade_near}")
                        await self._patch_fx(FX_HDR, map_scale, fade_near)
                        await self._set_effect(FX_HDR)
                        self.last_map_scale = map_scale
                        self.last_fade_near = fade_near
                    break
        else:
            for thr, map_scale in BRIGHTNESS_TABLE_SDR:
                if brightness > thr:
                    if self.last_map_scale != map_scale:
                        decky.logger.info(f"[MuraDeck] [Brightness] Updating SDR → Scale={map_scale}")
                        await self._patch_fx(FX_SDR, map_scale=map_scale)
                        await self._set_effect(FX_SDR)
                        self.last_map_scale = map_scale
                    break

    async def toggle_brightness(self, enable: bool):
        settings.setSetting("brightness_enabled", enable)
        settings.commit()
        self._brightness_enabled = enable
        decky.logger.info(f"[MuraDeck] Brightness State {'enabled' if enable else 'disabled'}")

        self.last_map_scale = None
        self.last_fade_near = None

        if self._enabled:
            await self.brightness_state(self.current_brightness or 0)

    async def get_brightness_enabled(self) -> bool:
        return self._brightness_enabled

    async def _log_watcher(self):
        for p in (LOG_CONSOLE, LOG_GAMEPROC):
            if not os.path.exists(p):
                decky.logger.warn(f"[MuraDeck] Log not found: {p}")

        proc = await asyncio.create_subprocess_exec(
            "tail", "-F", LOG_CONSOLE, LOG_GAMEPROC,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout

        re_appid      = re.compile(r"AppId=(\d+)")
        re_colorspace = re.compile(r"colorspace:.*(HDR10_ST2084|SRGB_NONLINEAR)")
        re_gamestop   = re.compile(r"game stopped")

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "ignore").rstrip()

            # AppId
            m = re_appid.search(text)
            if m:
                self.current_appid = m.group(1)
                decky.logger.info(f"[MuraDeck] [LogWatch] AppId={self.current_appid}")
                continue

            # Colorspace
            m = re_colorspace.search(text)
            if m:
                # HDR / SDR
                if "HDR10_ST2084" in m.group(1):
                    await self._apply_effect(FX_HDR, hdr=True)
                else:
                    await self._apply_effect(FX_SDR, hdr=False)
                continue

            # Game Stopped
            if re_gamestop.search(text):
                decky.logger.info("[LogWatch] Game stopped → revert to SDR")
                await self._apply_effect(FX_SDR, hdr=False)
                self.current_appid = None
                continue
    
    async def _ext_monitor_watcher(self):
        if not os.path.exists(LOG_DISPLAYMGR):
            decky.logger.warn("[MuraDeck] Log not found, failed to watch external monitor")
            return

        decky.logger.info("[MuraDeck] Starting external monitor watcher...")

        proc = await asyncio.create_subprocess_exec(
            "tail", "-Fn0", LOG_DISPLAYMGR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
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
                external_state = match.group(1)
                decky.logger.info(f"[MuraDeck] [Monitor Watcher] External state = {external_state}")

                if external_state == "1" and self._enabled:
                    decky.logger.info("[MuraDeck] [Monitor Watcher] External monitor connected → disabling plugin")
                    await self.toggle_enabled(False)
                elif external_state == "0" and not self._enabled:
                    decky.logger.info("[MuraDeck] [Monitor Watcher] External monitor disconnected → re-enabling plugin")
                    await self.toggle_enabled(True)

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

    async def _apply_effect(self, effect_file: str, hdr: bool):
        if hdr:
            self._grain_enabled = settings.getSetting("grain_enabled_hdr", True)
            self._lgg_enabled = settings.getSetting("lgg_enabled_hdr", True)
        else:
            self._grain_enabled = settings.getSetting("grain_enabled_sdr", True)
            self._lgg_enabled = settings.getSetting("lgg_enabled_sdr", True)

        self.current_effect = effect_file
        self.is_hdr = hdr
        decky.logger.info(f"[MuraDeck] [FX] Applying {'HDR' if hdr else 'SDR'} effect: {effect_file} (grain={self._grain_enabled}, lgg={self._lgg_enabled})")

        if self.current_brightness is not None:
            brightness = self.current_brightness
            if hdr:
                # Find map_scale dan fade_near dari table
                if self._brightness_enabled:
                    for thr, map_scale, fade_near in BRIGHTNESS_TABLE_HDR:
                        if brightness > thr:
                            if (self.last_map_scale != map_scale) or (self.last_fade_near != fade_near):
                                decky.logger.info(f"[MuraDeck] [Brightness] HDR → Scale={map_scale}, Fade={fade_near}")
                                await self._patch_fx(FX_HDR, map_scale, fade_near)
                                self.last_map_scale = map_scale
                                self.last_fade_near = fade_near
                            break
                else:
                    map_s, fade_n = STATIC_HDR
                    decky.logger.info(f"[MuraDeck] [Brightness=OFF] HDR static → Scale={map_s}, Fade={fade_n}")
                    await self._patch_fx(FX_HDR, map_s, fade_n)
            else:
                if self._brightness_enabled:
                    for thr, map_scale in BRIGHTNESS_TABLE_SDR:
                        if brightness > thr:
                            if self.last_map_scale != map_scale:
                                decky.logger.info(f"[MuraDeck] [Brightness] SDR → Scale={map_scale}")
                                await self._patch_fx(FX_SDR, map_scale=map_scale)
                                self.last_map_scale = map_scale
                            break
                else:
                    decky.logger.info(f"[MuraDeck] [Brightness=OFF] SDR static → Scale={STATIC_SDR}")
                    await self._patch_fx(FX_SDR, map_scale=STATIC_SDR)

        await self._set_effect(effect_file)

    async def toggle_grain(self, enable: bool):
        if self.is_hdr:
            settings.setSetting("grain_enabled_hdr", enable)
            self._grain_enabled_hdr = enable
        else:
            settings.setSetting("grain_enabled_sdr", enable)
            self._grain_enabled_sdr = enable
        settings.commit()
        self._grain_enabled = enable
        decky.logger.info(f"[MuraDeck] Grain toggled → {'ON' if enable else 'OFF'} for {'HDR' if self.is_hdr else 'SDR'} profile")
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_grain(self) -> bool:
        return self._grain_enabled

    async def toggle_lgg(self, enable: bool):
        if self.is_hdr:
            settings.setSetting("lgg_enabled_hdr", enable)
            self._lgg_enabled_hdr = enable
        else:
            settings.setSetting("lgg_enabled_sdr", enable)
            self._lgg_enabled_sdr = enable
        settings.commit()
        self._lgg_enabled = enable
        decky.logger.info(f"[MuraDeck] LGG toggled → {'ON' if enable else 'OFF'} for {'HDR' if self.is_hdr else 'SDR'} profile")
        await self._patch_fx(self.current_effect)
        await self._set_effect(self.current_effect)

    async def get_lgg(self) -> bool:
        return self._lgg_enabled

    async def _patch_fx(self, fx_name: str, map_scale: float | None = None, fade_near: float | None = None):
        path = os.path.join(FX_DIR, fx_name)
        if not os.path.isfile(path):
            decky.logger.error(f"[MuraDeck] FX file not found: {path}")
            return

        is_sdr = fx_name == FX_SDR

        if is_sdr:
            grain_value = 0.01 if self._grain_enabled else 0.0
            lgg_lift_value = 0.95 if self._lgg_enabled else 1.0
            lgg_gamma_value = 0.98 if self._lgg_enabled else 1.0
        else:
            grain_value = 0.01 if self._grain_enabled else 0.0
            if self._lgg_enabled:
                lgg_lift_value = "float3(1.0, 0.99, 1.0)"
                lgg_gamma_value = 1.0
            else:
                lgg_lift_value = 1.0
                lgg_gamma_value = 1.0

        with open(path, "r") as f:
            lines = f.readlines()

        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # MuraMapScale
            if map_scale is not None and "uniform float MuraMapScale" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float MuraMapScale < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.0; ui_max = 5;\n',
                    '\tui_label = "Mura Correction Strength";\n',
                    '\tui_tooltip = "Controls how aggresive mura map.";\n',
                    f'> = {map_scale};\n'
                ])
                continue

            # MuraFadeNearWhite
            if fade_near is not None and "uniform float MuraFadeNearWhite" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float MuraFadeNearWhite < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.1; ui_max = 20;\n',
                    '\tui_label = "Mura Fade Near White";\n',
                    '\tui_tooltip = "Controls how fast mura fix fades out to bright pixel. Higher = Faster fade.";\n',
                    f'> = {fade_near};\n'
                ])
                continue

            # Grain Intensity
            if "uniform float Intensity" in stripped:
                while i < len(lines) and ">" not in lines[i]:
                    i += 1
                i += 1
                out.extend([
                    'uniform float Intensity < __UNIFORM_SLIDER_FLOAT1\n',
                    '\tui_min = 0.0; ui_max = 1.0;\n',
                    '\tui_label = "Grain Intensity";\n',
                    '\tui_tooltip = "How visible the grain is. Higher is more visible.";\n',
                    f'> = {grain_value};\n'
                ])
                continue

            # RGB Lift
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

            # RGB Gamma
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

        # Generate temp file temp.fx
        temp_path = path.replace(".fx", "_temp.fx")
        try:
            shutil.copy(path, temp_path)
            decky.logger.info(f"[MuraDeck] [FXPatch] Temp effect created: {temp_path}")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] [FXPatch] Failed to copy temp effect: {e}")

        decky.logger.info(
            f"[MuraDeck] [FXPatch] {fx_name} patched → "
            f"Grain={grain_value}, LGG Lift/Gamma=({lgg_lift_value},{lgg_gamma_value})"
        )

    async def _clear_effect(self):
        cmd = 'export DISPLAY=:0 && xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u -set GAMESCOPE_RESHADE_EFFECT None'
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()
        if proc.returncode == 0:
            decky.logger.info("[MuraDeck] [xprop] Cleared ReShade effect")
        else:
            decky.logger.error(f"[MuraDeck] [xprop] Failed to clear effect: {err.decode().strip()}")

    async def direct_effect(self):
        decky.logger.info("[MuraDeck] [DirectFX] Applying effect instantly (no delay)")

        effect_name = self.current_effect or FX_SDR

        cmd = f'export DISPLAY=:0 && xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u -set GAMESCOPE_RESHADE_EFFECT {effect_name}'
        
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()

        if proc.returncode == 0:
            decky.logger.info(f"[MuraDeck] [DirectFX] Effect set to {effect_name}")
        else:
            decky.logger.error(f"[MuraDeck] [DirectFX] Error: {err.decode().strip()}")

    async def _set_effect(self, effect_name: str):
        temp_effect = effect_name.replace(".fx", "_temp.fx")
        cmd = f'export DISPLAY=:0 && xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u -set GAMESCOPE_RESHADE_EFFECT {temp_effect} && sleep 0.5 && xprop -root -f GAMESCOPE_RESHADE_EFFECT 8u -set GAMESCOPE_RESHADE_EFFECT {effect_name}'
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        _, err = await proc.communicate()
        if proc.returncode == 0:
            decky.logger.info(f"[MuraDeck] [xprop] Set effect {effect_name}")
        else:
            decky.logger.error(f"[MuraDeck] [xprop] Error: {err.decode().strip()}")

    async def check_shader_status(self) -> bool:
        shaders_exist = all(
            os.path.exists(os.path.join(SHADER_DIR, f)) for f in MURA_SHADER_FILES
        )
        textures_exist = all(
            os.path.exists(os.path.join(TEXTURE_DIR, f)) for f in MURA_TEXTURE_FILES
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

    # Function called first during the unload process, utilize this to handle your plugin being stopped, but not
    # completely removed
    async def _unload(self):
        decky.logger.info("[MuraDeck] Unloading...")
        pass

    # Function called after _unload during uninstall, utilize this to clean up processes and other remnants of your
    # plugin that may remain on the system
    async def _uninstall(self):
        settings.setSetting("has_seen_welcome", False)
        settings.commit()
        decky.logger.info("[MuraDeck] Reset has_seen_welcome flag on uninstall")

        # Remove shaders
        all_shader_files = MURA_SHADER_FILES + ["MuraDeck_SDR_temp.fx", "MuraDeck_HDR_temp.fx"]
        for file in all_shader_files:
            path = os.path.join(SHADER_DIR, file)
            try:
                os.remove(path)
                decky.logger.info(f"[MuraDeck] Deleted shader: {file}")
            except FileNotFoundError:
                pass
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Error deleting shader {file}: {e}")

        # Remove textures
        for file in MURA_TEXTURE_FILES:
            path = os.path.join(TEXTURE_DIR, file)
            try:
                os.remove(path)
                decky.logger.info(f"[MuraDeck] Deleted texture: {file}")
            except FileNotFoundError:
                pass
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Error deleting texture {file}: {e}")

        try:
            clear_task = asyncio.create_task(self._clear_effect())
            await asyncio.wait_for(clear_task, timeout=2.0)
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Failed to clear effect: {e}")

    # Migrations that should be performed before entering _main().
    async def _migration(self):
        decky.logger.info("[MuraDeck] Running migration step...")

        # Disable plugin by default after install
        enabled_setting = settings.getSetting("enabled", None)
        if enabled_setting is None:
            decky.logger.info("[MuraDeck] First-time install: disabling plugin")
            settings.setSetting("enabled", False)
            settings.commit()
            self._enabled = False
        else:
            self._enabled = enabled_setting

        os.makedirs(SHADER_DIR, exist_ok=True)
        os.makedirs(TEXTURE_DIR, exist_ok=True)

        missing_shader = any(
            not os.path.exists(os.path.join(SHADER_DIR, f)) for f in MURA_SHADER_FILES
        )
        missing_texture = any(
            not os.path.exists(os.path.join(TEXTURE_DIR, f)) for f in MURA_TEXTURE_FILES
        )

        if missing_shader or missing_texture:
            decky.logger.info("[MuraDeck] Shader or texture files missing, installing...")

            # Run both extractor and setup no matter what
            for cmd in ["galileo-mura-extractor", "galileo-mura-setup"]:
                try:
                    env = os.environ.copy()
                    env["DISPLAY"] = ":0"
                    proc = await asyncio.create_subprocess_exec(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env
                    )
                    stdout, stderr = await proc.communicate()
                    if proc.returncode == 0:
                        decky.logger.info(f"[MuraDeck] {cmd} finished successfully")
                    else:
                        decky.logger.error(f"[MuraDeck] {cmd} failed:\n{stderr.decode()}")
                except Exception as e:
                    decky.logger.error(f"[MuraDeck] Failed to run {cmd}: {e}")

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
                    decky.logger.warn("[MuraDeck] No valid fallback texture found in ~/.config/gamescope/mura")
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Failed to fallback copy from ~/.config/gamescope/mura: {e}")

            # Always copy shaders from plugin assets
            for file in MURA_SHADER_FILES:
                src = os.path.join(PLUGIN_SHADERS_DIR, file)
                dst = os.path.join(SHADER_DIR, file)
                try:
                    shutil.copy(src, dst)
                    os.chmod(dst, 0o644)
                    decky.logger.info(f"[MuraDeck] Installed shader file: {file}")
                except Exception as e:
                    decky.logger.error(f"[MuraDeck] Failed to install shader {file}: {e}")

        has_seen_welcome = settings.getSetting("has_seen_welcome", None)
        if has_seen_welcome is None:
            decky.logger.info("[MuraDeck] First-time install: marking welcome to be shown")
            settings.setSetting("has_seen_welcome", False)
            settings.commit()