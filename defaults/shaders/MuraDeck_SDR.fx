/**
 * MuraDeck
 * by RenvyRere ~ Moonveil-Kanata
 *
 * Fix Mura Effect on OLED Panel, by Combining Lift Gamma Gain and Film Grain as dithering on dark pixel, while Mura map on the bright pixel.
 */

#include "ReShadeUI.fxh"

// Lift Gamma Gain
uniform float3 RGB_Lift < __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Lift";
    ui_tooltip = "Adjust shadows.";
> = 0.95;

uniform float3 RGB_Gamma < __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.1; ui_max = 3.0;
    ui_label = "RGB Gamma";
    ui_tooltip = "Adjust midtones.";
> = 0.98;

uniform float3 RGB_Gain < __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Gain";
    ui_tooltip = "Adjust highlights.";
> = 1.0;

uniform int LggFadeNearBright < __UNIFORM_SLIDER_INT1
    ui_min = 0; ui_max = 16;
    ui_label = "LGG Fade Near Bright";
    ui_tooltip = "Higher values give less LGG to brighter pixels. Higher = Faster fade.";
> = 20;


// Grain
uniform float Intensity < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_label = "Grain Intensity";
    ui_tooltip = "How visible the grain is. Higher is more visible.";
> = 0.01;

uniform float Variance < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Controls the variance of the Gaussian noise. Lower values look smoother.";
> = 1.0;

uniform float Mean < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Affects the brightness of the noise.";
> = 0.5;

uniform int GrainFadeNearBright < __UNIFORM_SLIDER_INT1
    ui_min = 0; ui_max = 16;
    ui_label = "Grain Fade Near Bright";
    ui_tooltip = "Higher values give less grain to brighter pixels. Higher = Faster fade.";
> = 30;
uniform float GrainFadeNearBlack < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.1; ui_max = 8.0;
    ui_label = "Grain Fade Near Black";
    ui_tooltip = "Higher values give less grain to dark pixels. Higher = Faster fade.";
> = 0.03;

uniform float GrainBlackCutoff < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 0.1;
    ui_label = "Grain Black Cutoff";
    ui_tooltip = "Below this luminance, grain is fully disabled.";
> = 0.001;


// Mura Correction
uniform float MuraFadeNearBlack < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 8.0;
    ui_label = "Mura Fade Near Black";
    ui_tooltip = "Higher values give less mura to dark pixels. Higher = Faster fade.";
> = 0.02;

uniform float MuraBlackCutoff < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 0.1;
    ui_label = "Mura Black Cutoff";
    ui_tooltip = "Below this luma level, Mura correction is completely disabled.";
> = 0.01;

uniform float MuraMapScale < __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 5.0;
    ui_label = "Mura Correction Strength";
    ui_tooltip = "Controls how aggressive mura map.";
> = 0.0625;

texture red_tex < source = "red.png"; > { Width = 1280; Height = 800; Format = RGBA8; };
texture green_tex < source = "green.png"; > { Width = 1280; Height = 800; Format = RGBA8; };

sampler red_s { Texture = red_tex; };
sampler green_s { Texture = green_tex; };

uniform float Timer < source = "timer"; >;

#include "ReShade.fxh"

float3 MuraDeck(float4 vpos : SV_Position, float2 texcoord : TexCoord) : SV_Target
{
    float3 color = tex2D(ReShade::BackBuffer, texcoord).rgb;

    float luma = dot(color, float3(0.2126, 0.7152, 0.0722));
    if (luma <= 0.0001)
        return color;

    // GRAIN
    if (luma >= GrainBlackCutoff)
    {
        float inv_luma = dot(color, float3(-1.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0)) + 1.0;
        float stn = GrainFadeNearBright != 0 ? pow(abs(inv_luma), (float)GrainFadeNearBright) : 1.0;
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

        // Fade grain near black
        float fade_black = pow(saturate(luma), GrainFadeNearBlack);
        float fade_intensity = Intensity * fade_black;

        color += (gauss_noise1 - 0.5) * fade_intensity;
        color = saturate(color);
    }

    // LIFT GAMMA GAIN
    float3 color_LGG = color * (1.5 - 0.5 * RGB_Lift) + 0.5 * RGB_Lift - 0.5;
    color_LGG = saturate(color_LGG);
    color_LGG *= RGB_Gain;
    color_LGG = pow(abs(color_LGG), 1.0 / RGB_Gamma);
    color_LGG = saturate(color_LGG);

    float fade_lgg = LggFadeNearBright != 0 ? pow(1.0 - luma, (float)LggFadeNearBright) : 1.0;
    color = lerp(color, color_LGG, fade_lgg);

    // MURA CORRECTION
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
        mura_correction = saturate(mura_correction);

        // Fade mura fix near black
        float fade_mura = pow(saturate(luma), MuraFadeNearBlack);
        color = lerp(color, mura_correction, fade_mura);
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
