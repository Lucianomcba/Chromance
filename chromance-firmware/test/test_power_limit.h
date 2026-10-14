#ifndef TEST_POWER_LIMIT_H
#define TEST_POWER_LIMIT_H

namespace PowerTest {
constexpr double fixedCurrent = Constants::CONTROLLER_CURRENT_MA
    + Constants::NUM_OF_PIXELS * Constants::LED_IDLE_CURRENT_MA;

unsigned long latchedChannelSum(LedController &leds) {
    unsigned long total = 0;
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        for (uint32_t color : leds.getStrip(strip)->latchedPixels) {
            total += (color >> 16) & 255;
            total += (color >> 8) & 255;
            total += color & 255;
        }
    return total;
}

void fillStrip(LedController &leds, int strip) {
    for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment)
        for (int led = 0; led < Constants::LEDS_PER_SEGMENT; ++led) {
            const byte level = Topology::ledAssignments[segment][0] == strip ? 255 : 0;
            leds.setPixelColor(segment, led, level, level, level);
        }
}
}

void test_power_limit()
{
    TEST_CASE("Physical output includes dim channels, LED idle load and controller peaks");
    LedController leds;
    leds.begin();
    int observedShows = 0;
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        leds.getStrip(strip)->onShow = [&]() {
            ++observedShows;
            TEST_ASSERT(PowerTest::fixedCurrent + PowerTest::latchedChannelSum(leds) *
                (20.0 / 255.0) <= Constants::MAX_CURRENT_MA);
        };

    const byte levels[] = {0, 1, 12, 13, 24, 64, 160, 255};
    for (byte level : levels) {
        for (int s = 0; s < Constants::NUMBER_OF_SEGMENTS; ++s)
            for (int i = 0; i < Constants::LEDS_PER_SEGMENT; ++i)
                leds.setPixelColor(s, i, level, level, level);
        leds.show();
        const unsigned long channelSum = PowerTest::latchedChannelSum(leds);
        TEST_ASSERT(PowerTest::fixedCurrent + channelSum * (20.0 / 255.0) <= Constants::MAX_CURRENT_MA);
        TEST_ASSERT(leds.ledColors[0][0][0] == level);
        if (level > 0) {
            TEST_ASSERT(channelSum > 0);
        }
    }
    TEST_ASSERT(observedShows == 8 * Constants::NUMBER_OF_STRIPS);

    TEST_CASE("Strip redistribution stays within budget at every physical latch");
    // The old numerical strip order would latch blue's new bright frame before
    // black's old bright frame went dark, approximately doubling dynamic load.
    PowerTest::fillStrip(leds, Constants::BLACK_INDEX);
    leds.show();
    const unsigned long oldBlack = PowerTest::latchedChannelSum(leds);
    observedShows = 0;
    PowerTest::fillStrip(leds, Constants::BLUE_INDEX);
    leds.show();
    const unsigned long newBlue = PowerTest::latchedChannelSum(leds);
    TEST_ASSERT(PowerTest::fixedCurrent + (oldBlack + newBlue) *
        (20.0 / 255.0) > Constants::MAX_CURRENT_MA);
    TEST_ASSERT(observedShows == Constants::NUMBER_OF_STRIPS);

    // Cover both directions and unequal strip lengths. The onShow observer
    // inspects latched output, not the pending buffers filled before show().
    for (int source = 0; source < Constants::NUMBER_OF_STRIPS; ++source)
        for (int target = 0; target < Constants::NUMBER_OF_STRIPS; ++target) {
            if (source == target) continue;
            PowerTest::fillStrip(leds, source);
            leds.show();
            PowerTest::fillStrip(leds, target);
            leds.show();
        }

    // Clearing pending buffers must not forget the still-lit physical frame.
    leds.clear();
    PowerTest::fillStrip(leds, Constants::RED_INDEX);
    leds.show();
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        leds.getStrip(strip)->onShow = nullptr;
}

#endif
