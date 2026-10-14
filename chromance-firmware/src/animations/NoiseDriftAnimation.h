#ifndef NOISEDRIFTANIMATION_H
#define NOISEDRIFTANIMATION_H

#include "SmoothAnimation.h"

class NoiseDriftAnimation : public SmoothAnimation
{
public:
    NoiseDriftAnimation(AnimationController &controller)
        : SmoothAnimation(controller, Flow::SUNSET) {}

    const char *getName() const override { return "Noise Drift"; }

protected:
    Flow::Color sample(float x, float y, float time) const override;
};

#endif
