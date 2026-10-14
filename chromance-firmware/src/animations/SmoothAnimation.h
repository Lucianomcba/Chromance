#ifndef SMOOTH_ANIMATION_H
#define SMOOTH_ANIMATION_H

#include "Animation.h"
#include "FlowMath.h"

// Continuous effects share topology coordinates, fractional color interpolation,
// elapsed-time motion and controls. No per-frame allocation is needed.
class SmoothAnimation : public Animation {
public:
    SmoothAnimation(AnimationController& controller, int defaultPalette);
    void run() override;
    void update() override;
    bool isFinished() override { return false; }
    bool hasConfig() const override { return true; }
    void getConfig(JsonObject& doc) override;
    void setConfig(const JsonObject& doc) override;

protected:
    virtual Flow::Color sample(float x, float y, float time) const = 0;
    Flow::Color colorAt(float index) const {
        return Flow::samplePalette(currentPalette, index);
    }
    float scale = 1.0f;
    int palette;

private:
    float speed = 1.0f;
    int brightness = 160;
    double elapsedSeconds = 0.0;
    uint32_t lastFrame = 0;
    Flow::Color currentPalette[Flow::PALETTE_STOPS];
};

#endif
