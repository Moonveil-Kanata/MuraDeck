import { IconType } from "react-icons";
import { FaTabletAlt, FaFirstdraft, FaFlipboard, FaInfoCircle, FaBarcode, FaCuttlefish } from "react-icons/fa";

export type EffectKey = 'mura' | 'monitor' | 'brightness' | 'grain' | 'lgg' | 'loading';

export interface EffectMeta {
  title: string;
  desc: string;
  icon: IconType;
}

export const Desc: Record<EffectKey, EffectMeta> = {
  mura: {
    title: "Adaptive Mura Correction",
    desc: "Preserve black pixel, automatic HDR/SDR detection, and adaptive brightness correction.",
    icon: FaInfoCircle,
  },
  monitor: {
    title: "Respect External Monitor",
    desc: "Automatic turn the plugin on/off, when external monitor detected. Disable it if you want to fully deactivate the plugin",
    icon: FaTabletAlt,
  },
  brightness: {
    title: "Brightness Adaptation",
    desc: "Automatically adapt mura map correction based on current brightness",
    icon: FaBarcode,
  },
  grain: {
    title: "Dithering",
    desc: "Smooth out fading effects by using small amount of film grain on dark areas. Disable it if you find distracting",
    icon: FaFirstdraft,
  },
  lgg: {
    title: "Gamma Correction",
    desc: "Fix Samsung panel raised gamma by reducing lift and gamma only on dark areas. Disable it if you find it's too dark",
    icon: FaFlipboard,
  },
  loading: {
    title: "Processing...",
    desc: "Please wait...",
    icon: FaCuttlefish,
  },
};
