#include "ReShadeUI.fxh"

// === Grain Settings ===
uniform float Intensity <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_label = "Grain Intensity";
    ui_tooltip = "How visible the grain is. Higher is more visible.";
> = 1.0;

uniform float Variance <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Controls the variance of the Gaussian noise. Lower values look smoother.";
> = 0.9;

uniform float Mean <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Affects the brightness of the noise.";
> = 0.5;

uniform int GrainSignalToNoiseRatio <
    __UNIFORM_SLIDER_INT1
    ui_min = 0; ui_max = 1000;
    ui_label = "Grain Signal-to-Noise Ratio";
    ui_tooltip = "Higher values give less grain to brighter pixels. 0 disables this feature.";
> = 500;

uniform float GrainFadeNearBlack <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.1; ui_max = 8.0;
    ui_label = "Grain Fade Near Black";
    ui_tooltip = "Controls how fast grain fades to zero near black. Higher = Faster fade.";
> = 1;

// === Lift Gamma Gain Settings ===
uniform float3 RGB_Lift <
    __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Lift";
    ui_tooltip = "Adjust shadows.";
> = 0.9999;

uniform float3 RGB_Gamma <
    __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Gamma";
    ui_tooltip = "Adjust midtones.";
> = 0.99;

uniform float3 RGB_Gain <
    __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Gain";
    ui_tooltip = "Adjust highlights.";
> = 1.0;

// === Pre-Contrast untuk LGG ===
uniform float PreContrast <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.5; ui_max = 4.0;
    ui_label = "Pre-Contrast Boost";
    ui_tooltip = "Internal contrast boost before LGG (prevents washout).";
> = 1.0;

// === Virtual Contrast for Luminance (HDR-only) ===
uniform float LumaContrastBoost <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.5; ui_max = 4.0;
    ui_label = "Virtual Luma Contrast";
    ui_tooltip = "Boost contrast only for luminance detection, to help grain/LGG in HDR.";
> = 0.9998;

// === Mura Fix Settings ===
uniform float MuraFadeNearBlack <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 20.0;
    ui_label = "Mura Fade Near Black";
    ui_tooltip = "Controls how fast mura fix fades out to pure black. Higher = Faster fade.";
> = 0.05;

uniform float MuraFadeNearWhite <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.1; ui_max = 20.0;
    ui_label = "Mura Fade Near White";
    ui_tooltip = "Controls how fast mura fix fades out to bright pixel. Higher = Faster fade.";
> = 0;

uniform float MuraBlackCutoff <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 0.1;
    ui_label = "Mura Black Cutoff";
    ui_tooltip = "Below this luma level, Mura correction is completely disabled.";
> = 0.001;

uniform float MuraMapScale <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 5.0;
    ui_label = "Mura Correction Strength";
    ui_tooltip = "Controls how aggressive mura map.";
> = 0.0125;

texture red_tex < source = "red.png"; > { Width = 1280; Height = 800; Format = RGBA8; };
texture green_tex < source = "green.png"; > { Width = 1280; Height = 800; Format = RGBA8; };

sampler red_s { Texture = red_tex; };
sampler green_s { Texture = green_tex; };

uniform float Timer < source = "timer"; >;

#include "ReShade.fxh"

float3 MuraDeck(float4 vpos : SV_Position, float2 texcoord : TexCoord) : SV_Target
{
    float3 color = tex2D(ReShade::BackBuffer, texcoord).rgb;

    // === LUMINANCE UNTUK DETEKSI (pakai contrast detection tersendiri) ===
    float3 lum_contrasted = saturate((color - 0.5) * LumaContrastBoost + 0.5);
    float luma = dot(lum_contrasted, float3(0.2126, 0.7152, 0.0722));

    if (luma <= 0.0001)
        return color;

    // === GRAIN DENGAN CUT-OFF PADA WARNA GELAP ===
    {
        float inv_luma = dot(lum_contrasted, float3(-1.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0)) + 1.0;
        float stn = GrainSignalToNoiseRatio != 0 ? pow(abs(inv_luma), (float)GrainSignalToNoiseRatio) : 1.0;
        float variance = (Variance * Variance) * stn;
        float mean = Mean;

        const float PI = 3.1415927;
        float t = Timer * 0.0022337;
        float seed = dot(texcoord, float2(12.9898, 78.233));
        float sine = sin(seed);
        float cosine = cos(seed);
        float uniform_noise1 = frac(sine * 43758.5453 + t);
        float uniform_noise2 = frac(cosine * 53758.5453 - t);
        uniform_noise1 = max(uniform_noise1, 0.0001);

        float r = sqrt(-log(uniform_noise1));
        float theta = (2.0 * PI) * uniform_noise2;
        float gauss_noise1 = variance * r * cos(theta) + mean;

        float fade_black = pow(saturate(luma), GrainFadeNearBlack);
        float fade_intensity = Intensity * fade_black;

        color += (gauss_noise1 - 0.5) * fade_intensity;
    }

    // === LGG DENGAN PRE-CONTRAST (agar tidak wash-out) ===
    float3 pre_contrasted = max((color - 0.5) * PreContrast + 0.5, 0.0);
    float3 lgg = pre_contrasted * (1.5 - 0.5 * RGB_Lift) + 0.5 * RGB_Lift - 0.5;
    lgg *= RGB_Gain;
    lgg = max(lgg, 0.0);
    lgg = pow(lgg, 1.0 / RGB_Gamma);
    color = lgg;

    // === MURA FIX ===
    if (luma > MuraBlackCutoff)
    {
        const float target_aspect = 1280.0 / 800.0;
        float screen_aspect = ReShade::ScreenSize.x / ReShade::ScreenSize.y;
        float2 mura_uv = texcoord;

        if (screen_aspect > target_aspect)
        {
            float scale = target_aspect / screen_aspect;
            mura_uv.y = (mura_uv.y - 0.5) * scale + 0.5;
        }
        else
        {
            float scale = screen_aspect / target_aspect;
            mura_uv.x = (mura_uv.x - 0.5) * scale + 0.5;
        }

        float3 red = tex2D(red_s, mura_uv).rgb;
        float3 green = tex2D(green_s, mura_uv).rgb;

        float3 mura_correction = color;
        mura_correction.r += (red.r - 0.5) * MuraMapScale;
        mura_correction.g += (green.g - 0.5) * MuraMapScale;

        float fade_dark = pow(saturate(luma), MuraFadeNearBlack);
        float fade_bright = pow(1.0 - saturate(luma), MuraFadeNearWhite);
        float mura_blend = fade_dark * fade_bright;

        color = lerp(color, mura_correction, mura_blend);
    }

    return color;
}

technique MuraDeck
{
    pass
    {
        VertexShader = PostProcessVS;
        PixelShader = MuraDeck;
    }
}
