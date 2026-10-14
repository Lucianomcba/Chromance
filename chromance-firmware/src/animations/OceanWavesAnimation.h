#ifndef OCEANWAVESANIMATION_H
#define OCEANWAVESANIMATION_H

#include "SmoothAnimation.h"

class OceanWavesAnimation : public SmoothAnimation
{
public:
    OceanWavesAnimation(AnimationController &controller)
        : SmoothAnimation(controller, Flow::OCEAN) {}

    const char *getName() const override { return "Ocean Waves"; }

protected:
    Flow::Color sample(float x, float y, float time) const override;
};

#endif
