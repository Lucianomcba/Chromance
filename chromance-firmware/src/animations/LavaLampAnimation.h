#ifndef LAVALAMPANIMATION_H
#define LAVALAMPANIMATION_H

#include "SmoothAnimation.h"

class LavaLampAnimation : public SmoothAnimation
{
public:
    LavaLampAnimation(AnimationController &controller) : SmoothAnimation(controller, Flow::LAVA) {}

    const char *getName() const override { return "Lava Lamp"; }

protected:
    Flow::Color sample(float x, float y, float time) const override;

private:
    // Every LED in a frame shares its time, so compute the orbits once.
    mutable float orbitTime = -1.0f;
    mutable float blobX[4] = {};
    mutable float blobY[4] = {};
};

#endif
