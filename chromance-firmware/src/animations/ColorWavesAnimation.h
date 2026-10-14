#ifndef COLORWAVESANIMATION_H
#define COLORWAVESANIMATION_H

#include "SmoothAnimation.h"

class ColorWavesAnimation : public SmoothAnimation
{
public:
    ColorWavesAnimation(AnimationController &controller)
        : SmoothAnimation(controller, Flow::RAINBOW) {}

    const char *getName() const override { return "Color Waves"; }

protected:
    Flow::Color sample(float x, float y, float time) const override;
};

#endif
