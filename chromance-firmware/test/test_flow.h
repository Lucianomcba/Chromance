#ifndef TEST_FLOW_H
#define TEST_FLOW_H

#include "animations/AuroraAnimation.h"
#include "animations/ColorWavesAnimation.h"
#include "animations/LavaLampAnimation.h"
#include "animations/NoiseDriftAnimation.h"
#include "animations/OceanWavesAnimation.h"
#include "AnimationRegistry.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>

namespace FlowTest
{
using Frame = std::vector<byte>;

Frame capture(const LedController &leds)
{
    const byte *first = &leds.ledColors[0][0][0];
    return Frame(first, first + sizeof(leds.ledColors));
}

int maxDifference(const Frame &a, const Frame &b)
{
    int maximum = 0;
    for (size_t i = 0; i < a.size(); ++i)
        maximum = std::max(maximum, std::abs(int(a[i]) - int(b[i])));
    return maximum;
}

struct Fixture
{
    LedController leds;
    Configuration config;
    AnimationController controller;
    int index = -1;
    Animation *animation = nullptr;

    explicit Fixture(const char *name, unsigned long initialMillis = 0) : controller(leds, config)
    {
        reset_mocks();
        ArduinoMock::setMillis(initialMillis);
        leds.begin();
        controller.init();
        controller.setAutoSwitching(false);
        for (int i = 0; i < controller.getAnimationCount(); ++i)
        {
            if (std::strcmp(controller.getAnimation(i)->getName(), name) == 0)
            {
                index = i;
                animation = controller.getAnimation(i);
                controller.startAnimation(i);
                break;
            }
        }
    }

    void advance(unsigned long elapsed)
    {
        ArduinoMock::advanceMillis(elapsed);
        controller.update();
    }
};

bool continuousEndpoints(const LedController &leds)
{
    for (int node = 0; node < Constants::NUMBER_OF_NODES; ++node)
    {
        const byte *reference = nullptr;
        for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment)
        {
            for (int side = 0; side < Constants::SIDES_PER_SEGMENT; ++side)
            {
                if (Topology::segmentConnections[segment][side] != node)
                    continue;
                // The LED buffer is ordered from floor to ceiling.
                const int led = side == 0 ? Constants::LEDS_PER_SEGMENT - 1 : 0;
                const byte *color = leds.ledColors[segment][led];
                if (reference && std::memcmp(reference, color, 3) != 0)
                    return false;
                reference = color;
            }
        }
    }
    return true;
}

Frame frameAt(const char *name, unsigned long step, unsigned long duration)
{
    Fixture fixture(name);
    for (unsigned long elapsed = 0; elapsed < duration; elapsed += step)
        fixture.advance(std::min(step, duration - elapsed));
    return capture(fixture.leds);
}

void checkStableIds()
{
    TEST_CASE("Animation IDs preserve stored presets");
    const char *expected[] = {
        "BioPulseAnimation", "BouncingBallsAnimation", "CenterAnimation", "ChaseAnimation",
        "CubeAnimation", "DigitalRainAnimation", "FirefliesAnimation", "FireworksAnimation",
        "GlitchAnimation", "HeartbeatAnimation", "InfernoAnimation", "LightningAnimation",
        "MeteorShowerAnimation", "PlasmaAnimation", "RainbowAnimation", "RainbowPinwheelAnimation",
        "RainbowRadiateAnimation", "RandomAnimation", "SearchlightAnimation", "ShootingStarAnimation",
        "SnakeAnimation", "StarburstAnimation", "WaterAnimation", "WaveAnimation",
        "AuroraAnimation", "ColorWavesAnimation", "LavaLampAnimation", "NoiseDriftAnimation", "OceanWavesAnimation"
    };
    const auto entries = AnimationRegistry::getInstance().getSortedEntries();
    const size_t count = sizeof(expected) / sizeof(expected[0]);
    TEST_ASSERT(entries.size() == count);
    for (size_t id = 0; id < std::min(entries.size(), count); ++id)
        TEST_ASSERT(entries[id].name == expected[id]);
}

void checkSchedulerAndRollover(const char *name)
{
    TEST_CASE(std::string(name) + " auto scheduling and millis rollover");
    const Frame manual = frameAt(name, 20, 2300);
    Fixture automatic(name);
    automatic.controller.setAutoSwitching(true);
    for (unsigned long elapsed = 0; elapsed < 2300; elapsed += 20)
        automatic.advance(20);
    TEST_ASSERT(automatic.controller.getCurrentAnimation() == automatic.index);
    TEST_ASSERT(capture(automatic.leds) == manual);
    automatic.advance(27699);
    TEST_ASSERT(automatic.controller.getCurrentAnimation() == automatic.index);

    const Frame ordinary = frameAt(name, 20, 1000);
    Fixture wrapping(name, std::numeric_limits<uint32_t>::max() - 499u);
    for (int frame = 0; frame < 50; ++frame)
    {
        // Native unsigned long is wider than ESP32 millis: explicitly wrap
        // the mock clock to reproduce the physical device's 32-bit counter.
        ArduinoMock::setMillis(static_cast<uint32_t>(ArduinoMock::_millis + 20u));
        wrapping.controller.update();
    }
    TEST_ASSERT(capture(wrapping.leds) == ordinary);
}

void checkEffect(const char *name)
{
    TEST_CASE(name);
    Fixture fixture(name);
    TEST_ASSERT(fixture.animation != nullptr);
    if (!fixture.animation)
        return;

    JsonDocument defaultsDoc;
    JsonObject defaults = defaultsDoc.to<JsonObject>();
    fixture.animation->getConfig(defaults);
    TEST_ASSERT(fixture.animation->hasConfig());
    TEST_ASSERT(defaults["speed"].as<float>() == 1.0f);
    TEST_ASSERT(defaults["scale"].as<float>() == 1.0f);
    TEST_ASSERT(defaults["brightness"].as<int>() == 160);
    TEST_ASSERT(defaults["palette"].as<int>() >= 0 && defaults["palette"].as<int>() <= 4);

    const Frame initial = capture(fixture.leds);
    TEST_ASSERT(std::any_of(initial.begin(), initial.end(), [](byte value) { return value > 0; }));
    bool varied = false;
    for (size_t i = 3; i < initial.size(); i += 3)
        varied = varied || std::memcmp(initial.data(), initial.data() + i, 3) != 0;
    TEST_ASSERT(varied);
    TEST_ASSERT(continuousEndpoints(fixture.leds));

    fixture.advance(16);
    TEST_ASSERT(maxDifference(initial, capture(fixture.leds)) < 20);
    fixture.advance(984);
    TEST_ASSERT(maxDifference(initial, capture(fixture.leds)) > 2);
    TEST_ASSERT(continuousEndpoints(fixture.leds));

    // Manual scheduling must preserve elapsed phase past its 2-second trigger.
    fixture.advance(1300);
    const Frame scheduled = capture(fixture.leds);
    TEST_ASSERT(!fixture.animation->isFinished());
    TEST_ASSERT(fixture.controller.getCurrentAnimation() == fixture.index);
    TEST_ASSERT(maxDifference(initial, scheduled) > 2);
    TEST_ASSERT(scheduled == frameAt(name, 20, 2300));

    // Elapsed-time integration must not depend on the number of frames drawn.
    TEST_ASSERT(frameAt(name, 10, 1000) == frameAt(name, 20, 1000));

    // Reset the mock clock before a new fixture, rather than before advancing
    // the old fixture, whose last timestamp belongs to the previous clock.
    Fixture configured(name);
    JsonDocument inputDoc;
    JsonObject input = inputDoc.to<JsonObject>();
    input["speed"] = 0.0f;
    configured.animation->setConfig(input);
    const Frame frozen = capture(configured.leds);
    configured.advance(1000);
    TEST_ASSERT(frozen == capture(configured.leds));

    // A palette selection should blend even when motion is paused. Compare
    // the whole image so a single dark pixel cannot hide a hard color jump.
    input.clear();
    input["palette"] = (defaults["palette"].as<int>() + 1) % Flow::PALETTE_COUNT;
    configured.animation->setConfig(input);
    configured.controller.update();
    TEST_ASSERT(frozen == capture(configured.leds));
    configured.advance(16);
    TEST_ASSERT(maxDifference(frozen, capture(configured.leds)) < 20);
    configured.advance(984);
    TEST_ASSERT(maxDifference(frozen, capture(configured.leds)) > 2);
    TEST_ASSERT(continuousEndpoints(configured.leds));

    input.clear();
    input["speed"] = std::numeric_limits<float>::quiet_NaN();
    input["scale"] = std::numeric_limits<float>::quiet_NaN();
    configured.animation->setConfig(input);
    JsonDocument outputDoc;
    JsonObject output = outputDoc.to<JsonObject>();
    configured.animation->getConfig(output);
    TEST_ASSERT(std::isfinite(output["speed"].as<float>()));
    TEST_ASSERT(std::isfinite(output["scale"].as<float>()));

    input.clear();
    input["speed"] = 100.0f;
    input["scale"] = -100.0f;
    input["brightness"] = 1000;
    input["palette"] = 100;
    configured.animation->setConfig(input);
    output.clear();
    configured.animation->getConfig(output);
    TEST_ASSERT(output["speed"].as<float>() >= 0.0f && output["speed"].as<float>() <= 3.0f);
    TEST_ASSERT(output["scale"].as<float>() >= 0.25f && output["scale"].as<float>() <= 3.0f);
    TEST_ASSERT(output["brightness"].as<int>() >= 0 && output["brightness"].as<int>() <= 255);
    TEST_ASSERT(output["palette"].as<int>() >= 0 && output["palette"].as<int>() <= 4);

    input.clear();
    input["brightness"] = 0;
    configured.animation->setConfig(input);
    configured.advance(16);
    const Frame dark = capture(configured.leds);
    TEST_ASSERT(std::all_of(dark.begin(), dark.end(), [](byte value) { return value == 0; }));
}

void checkContrastCycle(const char *name)
{
    TEST_CASE(std::string(name) + " retains dark space and visible shapes across a minute");
    Fixture fixture(name);
    fixture.controller.update(); // Present the initial frame to the strips.
    bool darkSpace = true, visibleShape = true, visibleOutput = true;
    for (int step = 0; step <= 120; ++step) {
        if (step) fixture.advance(500);
        size_t black = 0, bright = 0;
        for (const auto& segment : fixture.leds.ledColors) {
            for (const auto& pixel : segment) {
                const int peak = std::max(int(pixel[0]), std::max(int(pixel[1]), int(pixel[2])));
                if (peak == 0) ++black;
                if (peak >= 20) ++bright;
            }
        }
        darkSpace = darkSpace && black >= Constants::NUM_OF_PIXELS / 4;
        visibleShape = visibleShape && bright >= Constants::NUM_OF_PIXELS / 20;
        int physicalPeak = 0;
        for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip) {
            auto* pixels = fixture.leds.getStrip(strip);
            for (int i = 0; i < pixels->numPixels(); ++i) {
                const uint32_t color = pixels->getPixelColor(i);
                physicalPeak = std::max(physicalPeak, int((color >> 16) & 255));
                physicalPeak = std::max(physicalPeak, int((color >> 8) & 255));
                physicalPeak = std::max(physicalPeak, int(color & 255));
            }
        }
        visibleOutput = visibleOutput && physicalPeak >= 8;
    }
    TEST_ASSERT(darkSpace);
    TEST_ASSERT(visibleShape);
    TEST_ASSERT(visibleOutput);
}
}

void test_smooth_animations()
{
    FlowTest::checkStableIds();
    TEST_CASE("Cyclic palette continuity");
    for (int palette = 0; palette < Flow::PALETTE_COUNT; ++palette)
    {
        const Flow::Color zero = Flow::palette(palette, 0.0f);
        const Flow::Color one = Flow::palette(palette, 1.0f);
        const Flow::Color below = Flow::palette(palette, -0.00001f);
        const Flow::Color above = Flow::palette(palette, 0.00001f);
        TEST_ASSERT(zero.r == one.r && zero.g == one.g && zero.b == one.b);
        TEST_ASSERT(std::fabs(below.r - above.r) < 0.02f &&
                    std::fabs(below.g - above.g) < 0.02f &&
                    std::fabs(below.b - above.b) < 0.02f);
    }

    const char *names[] = {"Aurora", "Color Waves", "Lava Lamp", "Noise Drift", "Ocean Waves"};
    for (const char *name : names)
    {
        FlowTest::checkEffect(name);
        FlowTest::checkSchedulerAndRollover(name);
        FlowTest::checkContrastCycle(name);
    }
}

#endif
