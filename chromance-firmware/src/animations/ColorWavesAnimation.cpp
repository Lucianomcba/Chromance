#include "ColorWavesAnimation.h"
#include "../AnimationRegistry.h"
#include <cmath>

REGISTER_ANIMATION(ColorWavesAnimation)

Flow::Color ColorWavesAnimation::sample(float x, float y, float time) const
{
    // Original two-dimensional interpretation of the slowly changing hue and
    // separate luminance waves in WLED Colorwaves and FastLED Pride2015.
    const float u = x * scale;
    const float v = y * scale;
    const float bend = 0.24f * std::sin(v * 2.3f + time * 0.31f)
                     + 0.12f * std::sin(u * 1.7f - time * 0.19f);
    const float wave = u * 0.37f + v * 0.18f + bend;
    const float hueDrift = time * 0.045f + 0.08f * std::sin(time * 0.13f);
    const Flow::Color color = colorAt(wave + hueDrift);

    // Separate bright ribbons with fully dark troughs so the diffuser does
    // not turn the entire field into an indistinct wash of color.
    const float crest = 0.5f + 0.5f * std::sin(
        Flow::TAU * (u * 0.48f - v * 0.62f + bend * 0.55f)
        - time * 0.85f);
    const float ribbon = Flow::smoothstep((crest - 0.48f) / 0.52f);
    const float luminance = ribbon * ribbon;
    return Flow::multiply(color, luminance);
}
