#include "LavaLampAnimation.h"
#include "../AnimationRegistry.h"
#include <cmath>

REGISTER_ANIMATION(LavaLampAnimation)

Flow::Color LavaLampAnimation::sample(float x, float y, float time) const
{
    if (orbitTime != time)
    {
        // Different slow periods let the blobs approach, merge and separate
        // without respawns or a visible common loop boundary.
        for (int i = 0; i < 4; ++i)
        {
            const float phase = i * Flow::TAU / 4.0f;
            blobX[i] = 0.70f * std::sin(time * (0.21f + i * 0.019f) + phase);
            blobY[i] = 0.90f * std::sin(time * (0.29f + i * 0.023f) + phase + 0.7f);
        }
        orbitTime = time;
    }

    x *= scale;
    y *= scale;
    float field = 0.0f;
    for (int i = 0; i < 4; ++i)
    {
        const float dx = x - blobX[i];
        const float dy = (y - blobY[i]) * 0.85f;
        const float radiusSquared = 0.07f + i * 0.014f;
        // A bounded rational falloff avoids singularities at blob centers.
        field += radiusSquared / (radiusSquared + dx * dx + dy * dy);
    }

    const float colorIndex = 0.23f + field * 0.21f + time * 0.008f;
    const Flow::Color lava = Flow::vivid(colorAt(colorIndex));
    // The low-density fluid is dark, rather than a colored background.
    // A smooth threshold keeps merging edges soft without filling the wall.
    const float coverage = Flow::smoothstep((field - 0.80f) / 0.55f);
    return Flow::multiply(lava, coverage);
}
