#include "AuroraAnimation.h"
#include "../AnimationRegistry.h"
#include <cmath>

REGISTER_ANIMATION(AuroraAnimation)

Flow::Color AuroraAnimation::sample(float x, float y, float time) const
{
    // Dark sky separates two curtains; diffuse tails otherwise light the
    // whole wall and hide their shape behind the physical diffuser.
    Flow::Color result = {0.0f, 0.0f, 0.0f};

    const float u = x * scale;
    for (int layer = 0; layer < 2; ++layer)
    {
        const float phase = static_cast<float>(layer) * 2.1f;
        const float drift = time * (0.38f + layer * 0.065f);
        const float bend = std::sin(u * 2.4f + drift + phase);
        const float fold = std::sin(u * 4.1f - drift * 0.63f + phase);
        const float center = -0.45f + layer * 0.85f + bend * 0.20f + fold * 0.075f;

        // A wider upper tail and softer lower lip resemble hanging light.
        // Smoothstep blends the widths continuously across the bright edge.
        const float height = y - center;
        const float upperTail = Flow::smoothstep(
            Flow::clamp01(0.5f - height * scale * 2.0f));
        const float width = (0.18f + upperTail * 0.16f) / scale;
        const float distance = std::fabs(height) / width;
        // Compact support reaches exactly black, with a smooth edge slope.
        const float envelope = Flow::smoothstep(1.0f - distance);

        const float ray = 0.5f + 0.5f * std::sin(
            u * (7.0f + layer * 1.3f) + bend * 1.6f - drift * 1.9f + phase);
        const float breathing = 0.85f + 0.15f * std::sin(time * 0.23f + phase);
        const float strength = (0.95f - layer * 0.10f) * envelope *
                               (0.30f + 0.70f * ray * ray) * breathing;
        const float colorPosition = 0.27f + layer * 0.22f + u * 0.07f +
                                    height * 0.17f + bend * 0.06f + time * 0.018f;
        const Flow::Color curtain = Flow::multiply(
            Flow::vivid(colorAt(colorPosition)), strength);
        result.r += curtain.r;
        result.g += curtain.g;
        result.b += curtain.b;
    }
    return result;
}
