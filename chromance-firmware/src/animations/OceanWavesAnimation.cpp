#include "OceanWavesAnimation.h"
#include "../AnimationRegistry.h"
#include <cmath>

REGISTER_ANIMATION(OceanWavesAnimation)

Flow::Color OceanWavesAnimation::sample(float x, float y, float time) const
{
    const float u = x * scale;
    const float v = y * scale;

    // Two broad diagonal crest bands cross the wall at the default scale.
    // A complete swell passes in about four seconds, with a gentle lateral
    // bend rather than random changes or discontinuities at segment junctions.
    const float bend = 0.30f * std::sin(1.7f * u + 0.8f * v + time * 0.22f);
    const float crest = 0.5f + 0.5f * std::sin(
        2.4f * u + 6.3f * v - time * 1.60f + bend);
    const float cross = 0.5f + 0.5f * std::sin(
        -4.2f * u + 2.5f * v - time * 0.70f + 1.7f);

    // Leave the troughs completely black for roughly a third of each swell.
    // Smoothstep has zero slope at the black edge, so the bands emerge gently
    // rather than switching on abruptly when they cross a pixel.
    const float ridge = Flow::smoothstep((crest - 0.25f) / 0.75f);
    const float luminance = 0.82f * ridge * (0.85f + 0.15f * cross);

    // Stay in the saturated blue/teal part of the ocean palette. Pale whitecaps
    // washed out the bands on the physical wall; crest shape supplies contrast.
    const float colorIndex = 0.08f + 0.35f * crest + 0.025f * cross;
    return Flow::multiply(colorAt(colorIndex), luminance);
}
