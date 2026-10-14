#ifndef TEST_TRANSITIONS_H
#define TEST_TRANSITIONS_H

#include "AnimationController.h"
#include "AnimationRegistry.h"
#include "RuntimeLock.h"
#include "animations/Animation.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>

namespace TransitionTest
{
struct Fixture
{
    LedController leds;
    Configuration config;
    AnimationController controller;

    Fixture() : controller(leds, config)
    {
        reset_mocks();
        leds.begin();
        controller.init();
        controller.setAutoSwitching(false);
    }

    int id(const char *name)
    {
        for (int i = 0; i < controller.getAnimationCount(); ++i)
            if (std::strcmp(controller.getAnimation(i)->getName(), name) == 0) return i;
        TEST_ASSERT(false); // Missing names must fail rather than silently selecting 255.
        return 255;
    }

    bool dark() const
    {
        const byte *first = &leds.ledColors[0][0][0];
        return std::all_of(first, first + sizeof(leds.ledColors),
                           [](byte value) { return value == 0; });
    }

    void seedLeftovers()
    {
        // Keep one real ripple alive throughout an automatic 30-second slot.
        Ripple &ripple = controller.getRipple(Constants::NUMBER_OF_RIPPLES - 1);
        ripple.start(3, 1, 0xFF0000, 0.0f, 100000, BEHAVIOR_ALWAYS_LEFT);
        Ripple::runnerNode = 12;
        leds.setPixelColor(39, 13, 60, 80, 100);
    }
};
}

void test_transitions()
{
    TEST_CASE("Different animation clears active ripples, runner and old pixels");
    for (bool useChange : {false, true})
    {
        TransitionTest::Fixture fixture;
        fixture.controller.startAnimation(fixture.id("Center Pulse"));
        fixture.seedLeftovers();
        TEST_ASSERT(fixture.controller.getActiveRippleCount() > 0);
        if (useChange) fixture.controller.changeAnimation(fixture.id("Wave"));
        else fixture.controller.startAnimation(fixture.id("Wave"));
        TEST_ASSERT(fixture.controller.getCurrentAnimation() == fixture.id("Wave"));
        TEST_ASSERT(fixture.controller.getActiveRippleCount() == 0);
        TEST_ASSERT(Ripple::runnerNode == -1);
        TEST_ASSERT(fixture.dark());
        fixture.controller.update();
        TEST_ASSERT(!fixture.dark());
    }

    TEST_CASE("Automatic transition uses the same cleanup as manual selection");
    {
        TransitionTest::Fixture fixture;
        const int center = fixture.id("Center Pulse"), wave = fixture.id("Wave");
        for (int i = 0; i < fixture.controller.getAnimationCount(); ++i)
        {
            JsonDocument doc;
            JsonObject config = doc.to<JsonObject>();
            config["enabled"] = i == center || i == wave;
            fixture.controller.getAnimation(i)->setConfig(config);
        }
        fixture.controller.recalculateAutoPulseTypes();
        fixture.controller.startAnimation(center);
        fixture.seedLeftovers();
        fixture.controller.setAutoSwitching(true);
        ArduinoMock::advanceMillis(Constants::RIPPLE_TIMEOUT);
        fixture.controller.update();
        TEST_ASSERT(fixture.controller.getCurrentAnimation() == wave);
        TEST_ASSERT(fixture.controller.getActiveRippleCount() == 0);
        TEST_ASSERT(Ripple::runnerNode == -1);
        TEST_ASSERT(fixture.dark());
    }

    TEST_CASE("Manual finite rerun preserves overlapping pulses and trails");
    {
        TransitionTest::Fixture fixture;
        const int center = fixture.id("Center Pulse");
        fixture.controller.startAnimation(center);
        fixture.seedLeftovers();
        Ripple &sentinel = fixture.controller.getRipple(Constants::NUMBER_OF_RIPPLES - 1);
        const unsigned long birthday = sentinel.birthday;
        ArduinoMock::advanceMillis(Constants::randomPulseTime);
        fixture.controller.update();
        TEST_ASSERT(fixture.controller.getCurrentAnimation() == center);
        TEST_ASSERT(sentinel.state != STATE_DEAD && sentinel.birthday == birthday);
        TEST_ASSERT(Ripple::runnerNode == 12);
        TEST_ASSERT(fixture.leds.ledColors[39][13][0] > 0);
        bool newPulse = false;
        for (int i = 0; i < Constants::NUMBER_OF_RIPPLES; ++i)
        {
            const Ripple &ripple = fixture.controller.getRipple(i);
            if (ripple.state != STATE_DEAD && ripple.birthday == millis()) newPulse = true;
        }
        TEST_ASSERT(newPulse);
        fixture.controller.startAnimation(center);
        TEST_ASSERT(sentinel.state != STATE_DEAD && sentinel.birthday == birthday);
        TEST_ASSERT(fixture.leds.ledColors[39][13][0] > 0);
    }

    TEST_CASE("Original stored animation IDs remain stable after transition repair");
    {
        const char *expected[] = {
            "BioPulseAnimation", "BouncingBallsAnimation", "CenterAnimation", "ChaseAnimation",
            "CubeAnimation", "DigitalRainAnimation", "FirefliesAnimation", "FireworksAnimation",
            "GlitchAnimation", "HeartbeatAnimation", "InfernoAnimation", "LightningAnimation",
            "MeteorShowerAnimation", "PlasmaAnimation", "RainbowAnimation", "RainbowPinwheelAnimation",
            "RainbowRadiateAnimation", "RandomAnimation", "SearchlightAnimation", "ShootingStarAnimation",
            "SnakeAnimation", "StarburstAnimation", "WaterAnimation", "WaveAnimation"
        };
        const auto entries = AnimationRegistry::getInstance().getSortedEntries();
        TEST_ASSERT(entries.size() >= 24);
        for (size_t id = 0; id < std::min(entries.size(), size_t(24)); ++id)
        {
            TEST_ASSERT(entries[id].name == expected[id]);
        }
    }

    TEST_CASE("Controller transitions share the recursive runtime lock across translation units");
    {
        TransitionTest::Fixture fixture;
        fixture.controller.startAnimation(fixture.id("Center Pulse"));
        std::atomic<bool> entered(false), completed(false);
        std::thread worker;
        {
            RuntimeLock outer;
            fixture.controller.setAutoSwitching(false); // Nested lock must work.
            worker = std::thread([&]() {
                entered.store(true);
                fixture.controller.changeAnimation(fixture.id("Wave"));
                completed.store(true);
            });
            while (!entered.load()) std::this_thread::yield();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            TEST_ASSERT(!completed.load());
            TEST_ASSERT(fixture.controller.getCurrentAnimation() == fixture.id("Center Pulse"));
        }
        worker.join();
        TEST_ASSERT(completed.load());
        TEST_ASSERT(fixture.controller.getCurrentAnimation() == fixture.id("Wave"));
    }
}

#endif
