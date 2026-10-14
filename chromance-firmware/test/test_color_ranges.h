#ifndef TEST_COLOR_RANGES_H
#define TEST_COLOR_RANGES_H

#include "animations/ColorConversion.h"
#include "AnimationController.h"
#include "Configuration.h"
#include "LedController.h"
#include <algorithm>
#include <cstring>
#include <limits>
#include <vector>

namespace ColorRangeTest
{
using Frame = std::vector<byte>;

Frame capture(const LedController &leds)
{
    const byte *first = &leds.ledColors[0][0][0];
    return Frame(first, first + sizeof(leds.ledColors));
}

Animation *find(AnimationController &controller, const char *name)
{
    for (int index = 0; index < controller.getAnimationCount(); ++index)
    {
        Animation *animation = controller.getAnimation(index);
        if (std::strcmp(animation->getName(), name) == 0)
        {
            controller.startAnimation(index);
            return animation;
        }
    }
    return nullptr;
}
}

void test_color_ranges()
{
    TEST_CASE("Hue wrapping and channel conversion boundaries");
    TEST_ASSERT(ColorConversion::hue(0.0f) == 0);
    TEST_ASSERT(ColorConversion::hue(65535.0f) == 65535);
    TEST_ASSERT(ColorConversion::hue(65536.0f) == 0);
    TEST_ASSERT(ColorConversion::hue(131073.0f) == 1);
    TEST_ASSERT(ColorConversion::hue(-1.0f) == 65535);
    TEST_ASSERT(ColorConversion::hue(-65536.0f) == 0);
    TEST_ASSERT(ColorConversion::hue(-65537.0f) == 65535);
    TEST_ASSERT(ColorConversion::hue(-0.000001f) == 0);
    TEST_ASSERT(ColorConversion::hue(std::numeric_limits<float>::infinity()) == 0);
    TEST_ASSERT(ColorConversion::hue(std::numeric_limits<float>::quiet_NaN()) == 0);
    TEST_ASSERT(ColorConversion::channel(-127.0f) == 0);
    TEST_ASSERT(ColorConversion::channel(0.0f) == 0);
    TEST_ASSERT(ColorConversion::channel(128.5f) == 128);
    TEST_ASSERT(ColorConversion::channel(255.0f) == 255);
    TEST_ASSERT(ColorConversion::channel(256.0f) == 255);
    TEST_ASSERT(ColorConversion::channel(std::numeric_limits<float>::infinity()) == 255);
    TEST_ASSERT(ColorConversion::channel(-std::numeric_limits<float>::infinity()) == 0);
    TEST_ASSERT(ColorConversion::channel(std::numeric_limits<float>::quiet_NaN()) == 0);

    const unsigned long timestamps[] = {0UL, 16UL, 2047UL, 2048UL, 2049UL, 10000UL, 0xFFFFFFF0UL};
    const char *names[] = {"Wave", "Plasma", "Rainbow Pinwheel", "Rainbow Radiate"};
    for (const char *name : names)
    {
        TEST_CASE(std::string(name) + " color conversion across time boundaries");
        reset_mocks();
        LedController leds;
        Configuration config;
        AnimationController controller(leds, config);
        leds.begin();
        controller.init();
        controller.setAutoSwitching(false);
        Animation *animation = ColorRangeTest::find(controller, name);
        TEST_ASSERT(animation != nullptr);
        if (!animation)
            continue;
        ColorRangeTest::Frame first;
        bool changed = false;
        for (unsigned long timestamp : timestamps)
        {
            ArduinoMock::setMillis(timestamp);
            animation->update();
            const auto frame = ColorRangeTest::capture(leds);
            TEST_ASSERT(std::any_of(frame.begin(), frame.end(), [](byte channel) { return channel != 0; }));
            // Conversion is deterministic at a fixed timestamp.
            animation->update();
            TEST_ASSERT(frame == ColorRangeTest::capture(leds));
            if (first.empty())
                first = frame;
            else
                changed = changed || frame != first;
        }
        TEST_ASSERT(changed);

        if (std::strcmp(name, "Rainbow Pinwheel") == 0)
        {
            TEST_CASE("Reverse pinwheel matches equivalent forward rotation");
            ArduinoMock::setMillis(2032UL);
            animation->update();
            const auto forward = ColorRangeTest::capture(leds);
            JsonDocument doc;
            JsonObject settings = doc.to<JsonObject>();
            settings["rotationDirection"] = -1;
            animation->setConfig(settings);
            ArduinoMock::setMillis(16UL);
            animation->update();
            TEST_ASSERT(forward == ColorRangeTest::capture(leds));
            JsonDocument outputDoc;
            JsonObject output = outputDoc.to<JsonObject>();
            animation->getConfig(output);
            TEST_ASSERT(output["rotationDirection"].as<int>() == -1);
            for (unsigned long timestamp : timestamps)
            {
                ArduinoMock::setMillis(timestamp);
                animation->update();
                const auto frame = ColorRangeTest::capture(leds);
                TEST_ASSERT(std::any_of(frame.begin(), frame.end(), [](byte channel) { return channel != 0; }));
            }
        }
        if (std::strcmp(name, "Rainbow Pinwheel") == 0 || std::strcmp(name, "Rainbow Radiate") == 0)
        {
            TEST_CASE(std::string(name) + " clamps configured brightness");
            config.setRainbowBrightness(-1);
            animation->update();
            const auto dark = ColorRangeTest::capture(leds);
            TEST_ASSERT(std::all_of(dark.begin(), dark.end(), [](byte channel) { return channel == 0; }));
            config.setRainbowBrightness(1000);
            animation->update();
            const auto bright = ColorRangeTest::capture(leds);
            const int ceiling = std::strcmp(name, "Rainbow Radiate") == 0 ? 40 : 255;
            TEST_ASSERT(*std::max_element(bright.begin(), bright.end()) == ceiling);
        }
    }
}

#endif
