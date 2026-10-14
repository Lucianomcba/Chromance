#ifndef AURORAANIMATION_H
#define AURORAANIMATION_H

#include "SmoothAnimation.h"

class AuroraAnimation : public SmoothAnimation
{
public:
    AuroraAnimation(AnimationController &controller)
        : SmoothAnimation(controller, Flow::AURORA) {}

    const char *getName() const override { return "Aurora"; }

protected:
    Flow::Color sample(float x, float y, float time) const override;
};

#endif
