#ifndef TEST_SLEEP_RACE_H
#define TEST_SLEEP_RACE_H

#include "helpers/SleepRaceValidation.h"

void test_sleep_race()
{
    TEST_CASE("A frame finishing after an unguarded blackout relights pixels");
    {
        reset_mocks();
        LedController leds;
        Configuration config;
        AnimationController controller(leds, config);
        leds.begin();
        controller.init();
        const auto result = SleepRaceValidation::run(leds, controller, false);
        TEST_ASSERT(!result.allPixelsBlack);
        TEST_ASSERT(!result.waitedForFrame);
    }
    TEST_CASE("The shared render barrier makes blackout the final physical output");
    for (int repeat = 0; repeat < 10; ++repeat) {
        reset_mocks();
        LedController leds;
        Configuration config;
        AnimationController controller(leds, config);
        leds.begin();
        controller.init();
        const auto result = SleepRaceValidation::run(leds, controller, true);
        TEST_ASSERT(result.waitedForFrame);
        TEST_ASSERT(result.allPixelsBlack);
        TEST_ASSERT(result.laterFrameBlocked);
    }
}

#endif
