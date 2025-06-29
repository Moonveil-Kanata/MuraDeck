import os
import subprocess
import re
import decky
import asyncio
import shutil
import glob

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

LOG_DIR = os.path.expanduser("~/.steam/steam/logs")
LOG_LINUX = os.path.join(LOG_DIR, "console-linux.txt")
LOG_GAMEPROC = os.path.join(LOG_DIR, "gameprocess_log.txt")
LOG_DISPLAYMGR = os.path.join(LOG_DIR, "systemdisplaymanager.txt")

FX_DIR = os.path.expanduser("~/.local/share/gamescope/reshade/Shaders")
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
    (40, 0.0125),
    (0,  0.065),
]


class Plugin:
    def __init__(self):
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
        self._monitor_watch_task = None

        self._grain_enabled_sdr = settings.getSetting("grain_enabled_sdr", True)
        self._lgg_enabled_sdr = settings.getSetting("lgg_enabled_sdr", True)
        self._grain_enabled_hdr = settings.getSetting("grain_enabled_hdr", True)
        self._lgg_enabled_hdr = settings.getSetting("lgg_enabled_hdr", True)

        self._grain_enabled = self._grain_enabled_sdr
        self._lgg_enabled = self._lgg_enabled_sdr

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

    async def _log_watcher(self):
        for p in (LOG_LINUX, LOG_GAMEPROC):
            if not os.path.exists(p):
                decky.logger.warn(f"[MuraDeck] Log not found: {p}")

        proc = await asyncio.create_subprocess_exec(
            "tail",
            "-F",
            LOG_LINUX,
            LOG_GAMEPROC,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout

        re_appid = re.compile(r"AppId=(\d+)")
        re_colorspace = re.compile(
            r"colorspace:.*(HDR10_ST2084|SRGB_NONLINEAR|SRGB_LINEAR)"
        )
        re_gamestop = re.compile(r"game stopped")

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
                cs = m.group(1)
                if cs == "HDR10_ST2084":
                    await self._set_profile("HDR10PQ")
                elif cs == "SRGB_LINEAR":
                    await self._set_profile("HDRscRGB")
                else:
                    await self._set_profile("SDR")
                continue

            # Game Stopped
            if re_gamestop.search(text):
                decky.logger.info("[LogWatch] Game stopped → revert to SDR")
                await self._set_profile("SDR")
                self.current_appid = None
                continue

    async def _ext_monitor_watcher(self):
        if not os.path.exists(LOG_DISPLAYMGR):
            decky.logger.warn(
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
                if state == "1" and self._enabled:
                    decky.logger.info("[Monitor] External → disabling")
                    await self.toggle_enabled(False)
                elif state == "0" and not self._enabled:
                    decky.logger.info("[Monitor] Internal → re-enabling")
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

    async def _patch_fx(self, fx_name: str, map_scale: float | None = None, fade_near: float | None = None):
        path = os.path.join(FX_DIR, fx_name)
        if not os.path.isfile(path):
            decky.logger.error(f"[MuraDeck] FX file not found: {path}")
            return

        is_sdr = (fx_name == FX_SDR)
        is_hdrscrgb = (fx_name == FX_HDRscRGB)
        
        if is_hdrscrgb:
            grain_value = 3.0 if self._grain_enabled else 0.0
            lgg_lift_value = 0.99995 if self._lgg_enabled else 1.0
            lgg_gamma_value = 1.0
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

        with open(path, "r") as f:
            lines = f.readlines()

        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

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
        )

    async def _clear_effect(self):
        cmd = (
            'export DISPLAY=:0 && '
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
            f'export DISPLAY=:0 && '
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
        temp = effect_name.replace(".fx", "_temp.fx")
        cmd = (
            f'export DISPLAY=:0 && '
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
        decky.logger.info("[MuraDeck] Installing shaders (forced reinstall)...")
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
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Run {cmd} error: {e}")

        # Keep install all shaders
        for fn in MURA_SHADER_FILES:
            src = os.path.join(PLUGIN_SHADERS_DIR, fn)
            dst = os.path.join(SHADER_DIR, fn)
            try:
                shutil.copy(src, dst)
                os.chmod(dst, 0o644)
                decky.logger.info(f"[MuraDeck] Installed shader {fn}")
            except Exception as e:
                decky.logger.error(f"[MuraDeck] Install shader {fn} error: {e}")

        # Install missing textures
        green_tmp = glob.glob(os.path.join(MURA_TMP_DIR, "*green.png"))
        red_tmp = glob.glob(os.path.join(MURA_TMP_DIR, "*red.png"))
        try:
            if not os.path.exists(os.path.join(TEXTURE_DIR, "green.png")) and green_tmp:
                shutil.copy(green_tmp[0], os.path.join(TEXTURE_DIR, "green.png"))
                decky.logger.info("[MuraDeck] Copied green.png")
            if not os.path.exists(os.path.join(TEXTURE_DIR, "red.png")) and red_tmp:
                shutil.copy(red_tmp[0], os.path.join(TEXTURE_DIR, "red.png"))
                decky.logger.info("[MuraDeck] Copied red.png")
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Copy tmp textures error: {e}")

        # Fallback ~/.config/gamescope/mura
        try:
            for cand in glob.glob(os.path.expanduser("~/.config/gamescope/mura/*")):
                g = glob.glob(os.path.join(cand, "*green.png"))
                r = glob.glob(os.path.join(cand, "*red.png"))
                if g and r:
                    if not os.path.exists(os.path.join(TEXTURE_DIR, "green.png")):
                        shutil.copy(g[0], os.path.join(TEXTURE_DIR, "green.png"))
                        decky.logger.info("[MuraDeck] Copied fallback green.png")
                    if not os.path.exists(os.path.join(TEXTURE_DIR, "red.png")):
                        shutil.copy(r[0], os.path.join(TEXTURE_DIR, "red.png"))
                        decky.logger.info("[MuraDeck] Copied fallback red.png")
                    break
        except Exception as e:
            decky.logger.error(f"[MuraDeck] Fallback texture copy error: {e}")

        # Welcome flag
        seen = settings.getSetting("has_seen_welcome", None)
        if seen is None:
            decky.logger.info("[MuraDeck] First-time: mark welcome")
            settings.setSetting("has_seen_welcome", False)
            settings.commit()
