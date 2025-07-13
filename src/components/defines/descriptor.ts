import { IconType } from "react-icons";
import { FaTabletAlt, FaFirstdraft, FaFlipboard, FaInfoCircle, FaBarcode, FaCuttlefish, FaBraille } from "react-icons/fa";

export type EffectKey = 'mura' | 'monitor' | 'brightness' | 'grain' | 'lgg' | 'aspectfix' | 'cas' | 'cas_slider' | 'loading';

export interface EffectMeta {
  title: string;
  desc: string;
  icon: IconType;
}

export const Desc: Record<EffectKey, EffectMeta> = {
  mura: {
    title: "Adaptive Mura Correction",
    desc: "Preserve black pixel, automatic HDR/SDR detection, and adaptive brightness correction.",
    icon: FaBraille,
  },
  monitor: {
    title: "Respect External Monitor",
    desc: "Automatically turn the plugin on/off, when external monitor detected. Disable it if you want to fully deactivate the plugin",
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
  aspectfix: {
    title: "Aspect ratio fix",
    desc: "By default mura map will be designed to be works with 16:xx ratio. Enabling this will adapt game ratios, for example 1:1 games",
    icon: FaFlipboard,
  },
  cas: {
    title: "AMD CAS",
    desc: "AMD's Contrast Adaptive Sharpening (CAS), enabling sharpening with optional upscaling to restore detail lost",
    icon: FaCuttlefish,
  },
  cas_slider: {
    title: "Sharpness",
    desc: "0 is default CAS, 1 is more sharpness",
    icon: FaCuttlefish,
  },
  loading: {
    title: "Processing...",
    desc: "Please wait...",
    icon: FaCuttlefish,
  },
};
