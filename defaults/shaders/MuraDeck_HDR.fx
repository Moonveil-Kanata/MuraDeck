/**
 * GrayLevelMuraFix version 1.0
 * by Renvy ~ Moonveil-Kanata
 *
 * Fix Mura Effect on OLED Panel, by Combining Lift Gamma Gain and Film Grain as dithering on dark pixel, while Mura map on the bright pixel.
 */

#include "ReShadeUI.fxh"

// === Grain Settings ===
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

uniform int SignalToNoiseRatio < __UNIFORM_SLIDER_INT1
	ui_min = 0; ui_max = 100;
	ui_label = "Signal-to-Noise Ratio";
	ui_tooltip = "Higher values give less grain to brighter pixels. 0 disables this feature.";
> = 90;

uniform float GrainFadeNearBlack < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.1; ui_max = 8.0;
	ui_label = "Grain Fade Near Black";
	ui_tooltip = "Controls how fast grain fades to zero near black. Higher = Faster fade.";
> = 0.175;

// === Lift Gamma Gain Settings ===
uniform float3 RGB_Lift < __UNIFORM_SLIDER_FLOAT3
	ui_min = 0.0; ui_max = 2.0;
	ui_label = "RGB Lift";
	ui_tooltip = "Adjust shadows.";
> = float3(1.0, 0.99, 1.0);

uniform float3 RGB_Gamma < __UNIFORM_SLIDER_FLOAT3
	ui_min = 0.1; ui_max = 3.0;
	ui_label = "RGB Gamma";
	ui_tooltip = "Adjust midtones.";
> = 1.0;

uniform float3 RGB_Gain < __UNIFORM_SLIDER_FLOAT3
	ui_min = 0.0; ui_max = 2.0;
	ui_label = "RGB Gain";
	ui_tooltip = "Adjust highlights.";
> = 1.0;

// === Virtual Contrast for Luminance ===
uniform float LumaContrastBoost < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.5; ui_max = 4.0;
	ui_label = "Virtual Luma Contrast";
	ui_tooltip = "Boost contrast only for luminance detection, to help grain/LGG in HDR.";
> = 1.01;

// === Mura Fix Settings ===
uniform float MuraFadeNearBlack < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0; ui_max = 20;
	ui_label = "Mura Fade Near Black";
	ui_tooltip = "Controls how fast mura fix fades out to pure black. Higher = Faster fade.";
> = 0;

uniform float MuraFadeNearWhite < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.1; ui_max = 20;
	ui_label = "Mura Fade Near White";
	ui_tooltip = "Controls how fast mura fix fades out to bright pixel. Higher = Faster fade.";
> = 4.75;

// === Mura Black Cutoff ===
uniform float MuraBlackCutoff < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.0; ui_max = 0.1;
	ui_label = "Mura Black Cutoff";
	ui_tooltip = "Below this luma level, Mura correction is completely disabled.";
> = 0.001;

uniform float MuraMapScale < __UNIFORM_SLIDER_FLOAT1
	ui_min = 0.0; ui_max = 5;
	ui_label = "Mura Correction Strength";
	ui_tooltip = "Controls how aggresive mura map.";
> = 0.3;

uniform int Type <
	ui_type = "combo";
	ui_items = "Defring\0";
> = 0;

texture red_tex < source = "red.png"; > {Width = 1280; Height = 800; Format = RGBA8;};
texture green_tex < source = "green.png"; > {Width = 1280; Height = 800; Format = RGBA8;};

sampler red_s { Texture = red_tex; };
sampler green_s { Texture = green_tex; };

uniform float Timer < source = "timer"; >;

#include "ReShade.fxh"

float3 FilmGrain_LGG_Mura(float4 vpos : SV_Position, float2 texcoord : TexCoord) : SV_Target
{
	// === ASPECT RATIO CORRECTION ===
	float screen_aspect = ReShade::ScreenSize.x / ReShade::ScreenSize.y;
	float target_aspect = 16.0 / 10.0;

	float2 mura_uv = texcoord;

	if (screen_aspect < target_aspect)
	{
		float new_width = screen_aspect / target_aspect;
		mura_uv.x = (texcoord.x - 0.5) * new_width + 0.5;
	}
	else if (screen_aspect > target_aspect)
	{
		float new_height = target_aspect / screen_aspect;
		mura_uv.y = (texcoord.y - 0.5) * new_height + 0.5;
	}

	// === ORIGINAL COLOR ===
	float3 color = tex2D(ReShade::BackBuffer, texcoord).rgb;

	// === CONTRASTED FOR LUMA ===
	float3 contrasted = saturate((color - 0.5) * LumaContrastBoost + 0.5);
	float luma = dot(contrasted, float3(0.2126, 0.7152, 0.0722));

	// === GRAIN ===
	float inv_luma = dot(contrasted, float3(-1.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0)) + 1.0;
	float stn = SignalToNoiseRatio != 0 ? pow(abs(inv_luma), (float)SignalToNoiseRatio) : 1.0;
	float variance = (Variance * Variance) * stn;
	float mean = Mean;

	const float PI = 3.1415927;
	float t = Timer * 0.0022337;
	float seed = dot(texcoord, float2(12.9898, 78.233));
	float sine = sin(seed);
	float cosine = cos(seed);
	float uniform_noise1 = frac(sine * 43758.5453 + t);
	float uniform_noise2 = frac(cosine * 53758.5453 - t);
	uniform_noise1 = (uniform_noise1 < 0.0001) ? 0.0001 : uniform_noise1;

	float r = sqrt(-log(uniform_noise1));
	r = (uniform_noise1 < 0.0001) ? PI : r;
	float theta = (2.0 * PI) * uniform_noise2;
	float gauss_noise1 = variance * r * cos(theta) + mean;

	float fade_black = pow(saturate(luma), GrainFadeNearBlack);
	float fade_intensity = Intensity * fade_black;
	color += (gauss_noise1 - 0.5) * fade_intensity;
	color = saturate(color);

	// === LGG ===
	float3 color_LGG = color * (1.5 - 0.5 * RGB_Lift) + 0.5 * RGB_Lift - 0.5;
	color_LGG = saturate(color_LGG);
	color_LGG *= RGB_Gain;
	color_LGG = pow(abs(color_LGG), 1.0 / RGB_Gamma);
	color_LGG = saturate(color_LGG);

	float fade_lgg = SignalToNoiseRatio != 0 ? pow(1.0 - luma, (float)SignalToNoiseRatio) : 1.0;
	color = lerp(color, color_LGG, fade_lgg);

	// === MURA ===
	if (luma > MuraBlackCutoff)
	{
		float3 red = tex2D(red_s, mura_uv).rgb;
		float3 green = tex2D(green_s, mura_uv).rgb;

		float kMuraMapScale = MuraMapScale;
		float3 mura_correction = color;
		mura_correction.r += (red.r - 0.5) * kMuraMapScale;
		mura_correction.g += (green.g - 0.5) * kMuraMapScale;

		// === Fade mura fix in shadows *and* highlights ===
		float fade_dark = pow(saturate(luma), MuraFadeNearBlack);
		float fade_bright = pow(1.0 - saturate(luma), MuraFadeNearWhite);
		float mura_blend = fade_dark * fade_bright;

		color = lerp(color, mura_correction, mura_blend);
	}

	return color;
}

technique FilmGrain_LGG_Mura
{
	pass
	{
		VertexShader = PostProcessVS;
		PixelShader = FilmGrain_LGG_Mura;
	}
}
