/**
 * MuraDeck
 * by RenvyRere ~ Moonveil-Kanata
 *
 * Fix Mura Effect on OLED Panel, by Combining Lift Gamma Gain and Film Grain as dithering on dark pixel, while Mura map on the bright pixel.
 */

#include "ReShadeUI.fxh"

// CAS
uniform float CAS_Enabled <
    ui_label = "Turn On/Off CAS";
    ui_tooltip = "0 := disable, to 1 := enable.";
    ui_min = 0.0; ui_max = 1.0;
    ui_step = 1.0;
> = 0.0;

uniform float Sharpness <
    ui_type = "drag";
    ui_label = "Sharpening strength";
    ui_tooltip = "0 := no sharpening, to 1 := full sharpening.";
    ui_min = 0.0; ui_max = 1.0;
> = 0.0;


// Pre-Contrast
uniform float LGGPreContrast <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.5; ui_max = 4.0;
    ui_label = "Lift Gamma Gain Pre-Contrast";
    ui_tooltip = "LGG Boost contrast to normalize HDR color profile.";
> = 1.0;

uniform float GlobalPreContrast <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.5; ui_max = 4.0;
    ui_label = "Global Pre-Contrast";
    ui_tooltip = "Pre-contrast to normalize HDR color profile.";
> = 0.9982;


// Lift Gamma Gain
uniform float3 RGB_Lift < __UNIFORM_SLIDER_FLOAT3
	ui_min = 0.0; ui_max = 2.0;
	ui_label = "RGB Lift";
	ui_tooltip = "Adjust shadows.";
> = 0.99995;

uniform float3 RGB_Gamma < __UNIFORM_SLIDER_FLOAT3
	ui_min = 0.1; ui_max = 3.0;
	ui_label = "RGB Gamma";
	ui_tooltip = "Adjust midtones.";
> = 1.0;

uniform float3 RGB_Gain <
    __UNIFORM_SLIDER_FLOAT3
    ui_min = 0.0; ui_max = 2.0;
    ui_label = "RGB Gain";
    ui_tooltip = "Adjust highlights.";
> = 1.0;


// Grain
uniform float Intensity < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.0; ui_max = 1.0;
	ui_label = "Grain Intensity";
	ui_tooltip = "How visible the grain is.";
> = 3.0;

uniform float Variance <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Controls the variance of the Gaussian noise. Lower values look smoother.";
> = 1.0;

uniform float Mean <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Affects the brightness of the noise.";
> = 0.5;

uniform int GrainFadeNearBright <
    __UNIFORM_SLIDER_INT1
    ui_min = 0; ui_max = 1000;
    ui_label = "Grain Fade Near Bright";
    ui_tooltip = "Higher values give less grain to brighter pixels. Higher = Faster fade.";
> = 500;

uniform float GrainFadeNearBlack <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.1; ui_max = 8.0;
    ui_label = "Grain Fade Near Black";
    ui_tooltip = "Higher values give less grain to dark pixels. Higher = Faster fade.";
> = 1.5;

uniform float GrainBlackCutoff <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 0.1;
    ui_label = "Grain Black Cutoff";
    ui_tooltip = "Grain will be disabled below this luminance level (absolute cutoff).";
> = 0.00091;


// Mura Correction
uniform float MuraFadeNearBright <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.1; ui_max = 20.0;
    ui_label = "Mura Fade Near White";
    ui_tooltip = "Higher values give less mura to brighter pixels. Higher = Faster fade.";
> = 0;

uniform float MuraFadeNearBlack <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 20.0;
    ui_label = "Mura Fade Near Black";
    ui_tooltip = "Higher values give less mura to dark pixels. Higher = Faster fade.";
> = 0.01;

uniform float MuraBlackCutoff <
    __UNIFORM_SLIDER_FLOAT1
    ui_min = 0.0; ui_max = 0.1;
    ui_label = "Mura Black Cutoff";
    ui_tooltip = "Below this luma level, Mura correction is completely disabled.";
> = 0.002;

uniform float MuraMapScale < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.0; ui_max = 5;
	ui_label = "Mura Correction Strength";
	ui_tooltip = "Controls how aggressive mura map.";
> = 0.0125;

texture red_tex < source = "red.png"; > { Width = 1280; Height = 800; Format = RGBA8; };
texture green_tex < source = "green.png"; > { Width = 1280; Height = 800; Format = RGBA8; };

sampler red_s { Texture = red_tex; };
sampler green_s { Texture = green_tex; };

uniform float Timer < source = "timer"; >;

#include "ReShade.fxh"

float3 SampleOffset(float2 texcoord, int2 offset)
{
    return tex2D(ReShade::BackBuffer, texcoord + ReShade::PixelSize * offset).rgb;
}

float3 ApplyCAS(float2 texcoord)
{
	if (CAS_Enabled <= 0.0)
	{
		return tex2D(ReShade::BackBuffer, texcoord).rgb;
	}

    float3 a = SampleOffset(texcoord, int2(-1, -1));
    float3 b = SampleOffset(texcoord, int2(0, -1));
    float3 c = SampleOffset(texcoord, int2(1, -1));
    float3 d = SampleOffset(texcoord, int2(-1, 0));
    float3 e = SampleOffset(texcoord, int2(0, 0));
    float3 f = SampleOffset(texcoord, int2(1, 0));
    float3 g = SampleOffset(texcoord, int2(-1, 1));
    float3 h = SampleOffset(texcoord, int2(0, 1));
    float3 i = SampleOffset(texcoord, int2(1, 1));

    float3 mnRGB = min(min(min(d, e), min(f, b)), h);
    mnRGB = min(mnRGB, min(min(a, c), min(g, i))) + mnRGB;

    float3 mxRGB = max(max(max(d, e), max(f, b)), h);
    mxRGB = max(mxRGB, max(max(a, c), max(g, i))) + mxRGB;

    float3 rcpMRGB = rcp(mxRGB);
    float3 ampRGB = saturate(min(mnRGB, 2.0 - mxRGB) * rcpMRGB);
    ampRGB = rsqrt(ampRGB);

    float peak = 8.0 - 3.0 * Sharpness;
    float3 wRGB = -rcp(ampRGB * peak);
    float3 rcpWeightRGB = rcp(1.0 + 4.0 * wRGB);

    float3 window = b + d + f + h;
    float3 outColor = (window * wRGB + e) * rcpWeightRGB;

    return outColor; // No saturate(), keep linear HDR values
}

float3 MuraDeck(float4 vpos : SV_Position, float2 texcoord : TexCoord) : SV_Target
{
    float3 color = ApplyCAS(texcoord);

    // PRE-CONTRAST
    float3 lum_contrasted = saturate((color - 0.5) * GlobalPreContrast + 0.5);
    float luma = dot(lum_contrasted, float3(0.2126, 0.7152, 0.0722));

    if (luma <= 0.0001)
        return color;

    // GRAIN
    if (luma > GrainBlackCutoff)
    {
        float inv_luma = dot(lum_contrasted, float3(-1.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0)) + 1.0;
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

        float fade_black = pow(saturate(luma), GrainFadeNearBlack);
        float fade_intensity = Intensity * fade_black;

        color += (gauss_noise1 - 0.5) * fade_intensity;
    }

    // LGG + PRE-CONTRAST
    float3 pre_contrasted = max((color - 0.5) * LGGPreContrast + 0.5, 0.0);
    float3 lgg = pre_contrasted * (1.5 - 0.5 * RGB_Lift) + 0.5 * RGB_Lift - 0.5;
    lgg *= RGB_Gain;
    lgg = max(lgg, 0.0);
    lgg = pow(lgg, 1.0 / RGB_Gamma);
    color = lgg;

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

        float fade_dark = pow(saturate(luma), MuraFadeNearBlack);
        float fade_bright = pow(1.0 - saturate(luma), MuraFadeNearBright);
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
