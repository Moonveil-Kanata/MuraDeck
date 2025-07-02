#include "ReShadeUI.fxh"

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
> = 1.0;

#include "ReShade.fxh"

float3 SampleOffset(float2 texcoord, int2 offset) {
	return tex2D(ReShade::BackBuffer, texcoord + ReShade::PixelSize * offset).rgb;
}

float3 CASPass(float4 vpos : SV_Position, float2 texcoord : TexCoord) : SV_Target
{
	if (CAS_Enabled <= 0.0)
	{
		return tex2D(ReShade::BackBuffer, texcoord).rgb;
	}
	
	// Sample neighborhood
	float3 a = SampleOffset(texcoord, int2(-1, -1));
	float3 b = SampleOffset(texcoord, int2(0, -1));
	float3 c = SampleOffset(texcoord, int2(1, -1));
	float3 d = SampleOffset(texcoord, int2(-1, 0));
	float3 e = SampleOffset(texcoord, int2(0, 0));
	float3 f = SampleOffset(texcoord, int2(1, 0));
	float3 g = SampleOffset(texcoord, int2(-1, 1));
	float3 h = SampleOffset(texcoord, int2(0, 1));
	float3 i = SampleOffset(texcoord, int2(1, 1));

	// Min and max computations
	float3 mnRGB = min(min(min(d, e), min(f, b)), h);
	mnRGB = min(mnRGB, min(min(a, c), min(g, i))) + mnRGB;

	float3 mxRGB = max(max(max(d, e), max(f, b)), h);
	mxRGB = max(mxRGB, max(max(a, c), max(g, i))) + mxRGB;

	// Compute sharpening weight
	float3 rcpMRGB = rcp(mxRGB);
	float3 ampRGB = saturate(min(mnRGB, 2.0 - mxRGB) * rcpMRGB);
	ampRGB = rsqrt(ampRGB);

	float peak = 8.0 - 3.0 * Sharpness;
	float3 wRGB = -rcp(ampRGB * peak);
	float3 rcpWeightRGB = rcp(1.0 + 4.0 * wRGB);

	float3 window = b + d + f + h;
	float3 outColor = saturate((window * wRGB + e) * rcpWeightRGB);

	return outColor;
}

technique ContrastAdaptiveSharpen
{
	pass
	{
		VertexShader = PostProcessVS;
		PixelShader = CASPass;
	}
}
