#ifndef TEST_SLEEP_SHUTDOWN_H
#define TEST_SLEEP_SHUTDOWN_H

namespace SleepShutdownTest {
bool allPhysicalPixelsBlack(LedController &leds)
{
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        for (uint32_t color : leds.getStrip(strip)->latchedPixels)
            if (color != 0) return false;
    return true;
}
}

void test_sleep_shutdown()
{
    TEST_CASE("A lost one-shot blackout leaves powered LEDs lit; shutdown retries recover");
    LedController leds;
    leds.begin();
    // Seed every physical pixel, not just a sample of the logical topology.
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip) {
        auto *physical = leds.getStrip(strip);
        for (int pixel = 0; pixel < physical->numPixels(); ++pixel)
            physical->setPixelColor(pixel, 0x010203);
        physical->show();
    }

    int attempts[Constants::NUMBER_OF_STRIPS] = {};
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip) {
        auto *physical = leds.getStrip(strip);
        const auto previous = physical->latchedPixels;
        physical->onShow = [&, strip, physical, previous]() {
            // A driver returning from show() does not prove a valid wire frame.
            // Model a missed first black transfer retaining the prior output.
            if (++attempts[strip] == 1) physical->latchedPixels = previous;
        };
    }
    // Reproduce the old shutdown's behavior under the fault injection.
    leds.clear();
    leds.show();
    TEST_ASSERT(!SleepShutdownTest::allPhysicalPixelsBlack(leds));
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        attempts[strip] = 0;

    const unsigned long started = millis();
    leds.prepareForDeepSleep();
    TEST_ASSERT(SleepShutdownTest::allPhysicalPixelsBlack(leds));
    TEST_ASSERT(millis() - started >= 6);
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip) {
        TEST_ASSERT(attempts[strip] == 3);
        for (uint32_t color : leds.getStrip(strip)->pixels)
            TEST_ASSERT(color == 0);
        leds.getStrip(strip)->onShow = nullptr;
    }
    for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment)
        for (int pixel = 0; pixel < Constants::LEDS_PER_SEGMENT; ++pixel)
            for (int channel = 0; channel < 3; ++channel)
                TEST_ASSERT(leds.ledColors[segment][pixel][channel] == 0);

    TEST_CASE("Normal output can resume after a shutdown blackout");
    leds.begin();
    leds.setPixelColor(0, 0, 1, 2, 3);
    leds.show();
    TEST_ASSERT(!SleepShutdownTest::allPhysicalPixelsBlack(leds));
}

#endif
