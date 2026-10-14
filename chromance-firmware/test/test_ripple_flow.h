#ifndef TEST_RIPPLE_FLOW_H
#define TEST_RIPPLE_FLOW_H

#include "ripple.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace RippleFlowTest
{
struct Snapshot
{
    RippleState state;
    int segment;
    int led;
    std::vector<byte> colors;
};

Snapshot run(unsigned long step, unsigned long duration, bool up)
{
    reset_mocks();
    LedController leds;
    leds.begin();
    Ripple ripple;
    // Actual node/direction starts on segment 0 in either travel direction.
    ripple.start(up ? 3 : 0, up ? 1 : 4, 0xC87828, 0.5f, 2000, BEHAVIOR_LAZY);
    for (unsigned long elapsed = 0; elapsed < duration; elapsed += step)
    {
        ArduinoMock::advanceMillis(std::min(step, duration - elapsed));
        leds.clear();
        ripple.advance(leds);
    }
    const byte *first = &leds.ledColors[0][0][0];
    return {ripple.state, ripple.node, ripple.direction,
            std::vector<byte>(first, first + sizeof(leds.ledColors))};
}

bool isDark(const LedController &leds)
{
    const byte *first = &leds.ledColors[0][0][0];
    return std::all_of(first, first + sizeof(leds.ledColors),
                       [](byte value) { return value == 0; });
}
}

void test_ripple_flow()
{
    TEST_CASE("Ripple fractional intensity in both directions");
    for (bool up : {true, false})
    {
        reset_mocks();
        LedController leds;
        leds.begin();
        Ripple ripple;
        ripple.start(up ? 3 : 0, up ? 1 : 4, 0xC87828, 1.0f, 1000, BEHAVIOR_LAZY);
        ArduinoMock::advanceMillis(30);
        ripple.advance(leds);
        const int current = up ? 0 : Constants::LEDS_PER_SEGMENT - 1;
        const int next = up ? 1 : Constants::LEDS_PER_SEGMENT - 2;
        TEST_ASSERT(ripple.state == (up ? STATE_TRAVEL_UP : STATE_TRAVEL_DOWN));
        TEST_ASSERT(ripple.node == 0 && ripple.direction == current);
        // Integral distance is 1.4775; the first state step enters the segment.
        // Age brightness is .97, so rounded red intensity 194 is shared 101/93.
        TEST_ASSERT(leds.ledColors[0][current][0] == 101);
        TEST_ASSERT(leds.ledColors[0][next][0] == 93);
        TEST_ASSERT(leds.ledColors[0][current][1] + leds.ledColors[0][next][1] == 116);
        TEST_ASSERT(leds.ledColors[0][current][2] + leds.ledColors[0][next][2] == 39);
    }

    TEST_CASE("Ripple elapsed movement and intensity across frame cadences");
    for (bool up : {true, false})
    {
        const auto reference = RippleFlowTest::run(10, 200, up);
        for (unsigned long step : {20UL, 50UL, 200UL})
        {
            const auto other = RippleFlowTest::run(step, 200, up);
            TEST_ASSERT(reference.state == other.state);
            TEST_ASSERT(reference.segment == other.segment);
            TEST_ASSERT(reference.led == other.led);
            TEST_ASSERT(reference.colors == other.colors);
        }
        // A delayed frame lights only the two current samples, not skipped LEDs.
        int litPixels = 0;
        for (size_t i = 0; i < reference.colors.size(); i += 3)
            litPixels += reference.colors[i] != 0;
        TEST_ASSERT(litPixels == 2);
    }

    TEST_CASE("Ripple lifespan expires before catch-up and zero lifespan is safe");
    reset_mocks();
    LedController leds;
    leds.begin();
    Ripple expired;
    expired.start(3, 1, 0xFFFFFF, 1000000.0f, 100, BEHAVIOR_ALWAYS_LEFT);
    ArduinoMock::advanceMillis(100);
    expired.advance(leds);
    TEST_ASSERT(expired.state == STATE_DEAD);
    TEST_ASSERT(RippleFlowTest::isDark(leds));
    expired.start(3, 1, 0xFFFFFF, 1.0f, 0, BEHAVIOR_LAZY);
    ArduinoMock::advanceMillis(1);
    expired.advance(leds);
    TEST_ASSERT(expired.state == STATE_DEAD);
    TEST_ASSERT(RippleFlowTest::isDark(leds));

    TEST_CASE("Ripple rejects unreasonable catch-up and invalid public position");
    expired.start(3, 1, 0xFFFFFF, 1000000.0f, 10000, BEHAVIOR_ALWAYS_LEFT);
    ArduinoMock::advanceMillis(1);
    expired.advance(leds);
    TEST_ASSERT(expired.state == STATE_DEAD);
    TEST_ASSERT(RippleFlowTest::isDark(leds));
    expired.start(3, 1, 0xFFFFFF, 1.0f, 1000, BEHAVIOR_LAZY);
    expired.node = Constants::NUMBER_OF_NODES;
    expired.advance(leds);
    TEST_ASSERT(expired.state == STATE_DEAD);

    TEST_CASE("Ripple directly initialized Fireworks slot resets old progress");
    reset_mocks();
    expired.start(3, 1, 0xFFFFFF, 1.0f, 1000, BEHAVIOR_LAZY);
    ArduinoMock::advanceMillis(100);
    expired.advance(leds);
    // Mirror the existing Fireworks direct initialization after reusing a slot.
    expired.state = STATE_TRAVEL_UP;
    expired.node = 0;
    expired.direction = 5;
    expired.birthday = millis();
    expired.speed = 1.0f;
    expired.lifespan = 1000;
    leds.clear();
    ArduinoMock::advanceMillis(10);
    expired.advance(leds);
    TEST_ASSERT(expired.state == STATE_TRAVEL_UP && expired.direction == 5);
    TEST_ASSERT(leds.ledColors[0][5][0] > 0 && leds.ledColors[0][6][0] > 0);

    TEST_CASE("Ripple uint32 timer rollover");
    reset_mocks();
    leds.clear();
    ArduinoMock::setMillis(0xFFFFFFF0UL);
    Ripple rolled;
    rolled.start(3, 1, 0xC87828, 1.0f, 1000, BEHAVIOR_LAZY);
    ArduinoMock::setMillis(14UL); // 30 ms after birthday across rollover.
    rolled.advance(leds);
    TEST_ASSERT(rolled.state == STATE_TRAVEL_UP);
    TEST_ASSERT(rolled.node == 0 && rolled.direction == 0);
    TEST_ASSERT(leds.ledColors[0][0][0] == 101 && leds.ledColors[0][1][0] == 93);
    leds.clear();
    ArduinoMock::setMillis(984UL); // Exactly 1000 ms after birthday.
    rolled.advance(leds);
    TEST_ASSERT(rolled.state == STATE_DEAD);
    TEST_ASSERT(RippleFlowTest::isDark(leds));

    TEST_CASE("Ripple original lazy and couch potato stops at next node");
    for (RippleBehavior behavior : {BEHAVIOR_LAZY, BEHAVIOR_COUCH_POTATO})
    {
        reset_mocks();
        Ripple stopping;
        stopping.start(3, 1, 0xFFFFFF, 2.0f, 10000, behavior);
        ArduinoMock::advanceMillis(180);
        leds.clear();
        stopping.advance(leds);
        TEST_ASSERT(stopping.state == STATE_DEAD);
        TEST_ASSERT(RippleFlowTest::isDark(leds));
    }
}

#endif
