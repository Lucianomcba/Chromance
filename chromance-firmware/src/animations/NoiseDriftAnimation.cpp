#include "NoiseDriftAnimation.h"
#include "../AnimationRegistry.h"
#include <cmath>
#include <cstdint>

REGISTER_ANIMATION(NoiseDriftAnimation)

namespace
{
float latticeValue(int x, int y, int z)
{
    // Unsigned arithmetic has defined wraparound, including negative cells.
    uint32_t hash = static_cast<uint32_t>(x) * 0x8da6b343u
                  ^ static_cast<uint32_t>(y) * 0xd8163841u
                  ^ static_cast<uint32_t>(z) * 0xcb1ab31fu;
    hash ^= hash >> 16;
    hash *= 0x7feb352du;
    hash ^= hash >> 15;
    hash *= 0x846ca68bu;
    hash ^= hash >> 16;
    return static_cast<float>(hash >> 8) * (1.0f / 16777215.0f);
}

float fade(float value)
{
    // Quintic interpolation keeps both velocity and acceleration continuous
    // as the sampling point passes between deterministic lattice cells.
    return value * value * value * (value * (value * 6.0f - 15.0f) + 10.0f);
}

float lerp(float a, float b, float amount)
{
    return a + (b - a) * amount;
}

float valueNoise(float x, float y, float z)
{
    const int ix = static_cast<int>(std::floor(x));
    const int iy = static_cast<int>(std::floor(y));
    const int iz = static_cast<int>(std::floor(z));
    const float fx = fade(x - ix);
    const float fy = fade(y - iy);
    const float fz = fade(z - iz);
    const float lower = lerp(
        lerp(latticeValue(ix, iy, iz), latticeValue(ix + 1, iy, iz), fx),
        lerp(latticeValue(ix, iy + 1, iz), latticeValue(ix + 1, iy + 1, iz), fx), fy);
    const float upper = lerp(
        lerp(latticeValue(ix, iy, iz + 1), latticeValue(ix + 1, iy, iz + 1), fx),
        lerp(latticeValue(ix, iy + 1, iz + 1), latticeValue(ix + 1, iy + 1, iz + 1), fx), fy);
    return lerp(lower, upper, fz);
}
}

Flow::Color NoiseDriftAnimation::sample(float x, float y, float time) const
{
    // An original palette-cloud effect inspired by WLED Noise Pal. Smooth,
    // bounded paths advect a coherent 3D field without wrapping its position
    // or replacing random values between frames.
    const float u = x * scale * 1.65f + 3.6f * std::sin(time * 0.085f);
    const float v = y * scale * 1.65f + 3.0f * std::sin(time * 0.067f + 1.7f);
    const float depth = 2.4f * std::sin(time * 0.049f + 0.6f);
    const float broad = valueNoise(u, v, depth);
    const float detail = valueNoise(u * 2.0f + 13.7f, v * 2.0f - 9.2f,
                                    depth * 1.4f + 4.3f);
    const float cloud = Flow::clamp01(broad * 0.82f + detail * 0.18f);
    const float colorDrift = 0.12f * std::sin(time * 0.041f);
    Flow::Color color = colorAt(cloud * 1.25f + colorDrift);

    // Remove most of the common RGB component so diffuse reflections retain
    // the selected palette's hue instead of appearing pale. Normalize the
    // colored crest; the cloud mask, rather than palette darkness, defines
    // its silhouette. Palette transitions still go through colorAt().
    const float neutral = std::fmin(color.r, std::fmin(color.g, color.b)) * 0.85f;
    color.r -= neutral;
    color.g -= neutral;
    color.b -= neutral;
    const float peak = std::fmax(color.r, std::fmax(color.g, color.b));
    if (peak > 0.0f)
        color = Flow::multiply(color, 230.0f / peak);

    // A broad eased edge surrounds distinct cloud islands. Below the edge
    // the wall is black, giving moving crests visible negative space and
    // lowering average light output compared with the previous 36% floor.
    const float island = Flow::smoothstep((cloud - 0.48f) / 0.32f);
    const float luminance = 0.85f * island * island;
    return Flow::multiply(color, luminance);
}
