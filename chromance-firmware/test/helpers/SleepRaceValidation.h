#ifndef SLEEP_RACE_VALIDATION_H
#define SLEEP_RACE_VALIDATION_H

#include "AnimationController.h"
#include "RuntimeLock.h"
#include "animations/Animation.h"
#include <atomic>
#include <chrono>
#include <cstring>
#include <future>
#include <thread>

namespace SleepRaceValidation {
struct Result {
    bool waitedForFrame;
    bool allPixelsBlack;
    bool laterFrameBlocked;
};

// Exercise real controller output, blackout and the shared RuntimeLock. The
// host gate models main.cpp's sleepRequested state; it does not emulate RMT,
// WiFi, GPIO retention, or the ESP32 sleep instruction.
inline Result run(LedController& leds, AnimationController& controller, bool useBarrier)
{
    int effect = -1;
    for (int i = 0; i < controller.getAnimationCount(); ++i)
        if (std::strcmp(controller.getAnimation(i)->getName(), "Color Waves") == 0) effect = i;
    if (effect < 0) return {false, false, false};
    controller.setAutoSwitching(false);
    controller.startAnimation(effect);

    std::promise<void> frameHeld, finishFrame, requestAttempted, blackoutDone;
    auto frameHeldFuture = frameHeld.get_future();
    auto finishFrameFuture = finishFrame.get_future();
    auto requestAttemptedFuture = requestAttempted.get_future();
    auto blackoutDoneFuture = blackoutDone.get_future();
    std::atomic<bool> sleepPublished(false), blackoutCompleted(false);

    std::thread renderer([&]() {
        RuntimeLock guard;
        controller.update();
        frameHeld.set_value();
        // Freeze an in-flight frame. Its final write deliberately happens
        // after the other thread has attempted to request shutdown.
        finishFrameFuture.wait();
        controller.update();
    });
    frameHeldFuture.wait();

    std::thread shutdown([&]() {
        requestAttempted.set_value();
        auto blackout = [&]() {
            sleepPublished.store(true);
            leds.prepareForDeepSleep();
            blackoutCompleted.store(true);
            blackoutDone.set_value();
        };
        if (useBarrier) {
            RuntimeLock guard;
            blackout();
        } else blackout();
    });
    requestAttemptedFuture.wait();
    bool waitedForFrame;
    if (useBarrier) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        waitedForFrame = !blackoutCompleted.load();
    } else {
        // Deterministic broken control: blackout finishes first, then the
        // already-started frame overwrites it. No simultaneous buffer access.
        blackoutDoneFuture.wait();
        waitedForFrame = false;
    }
    finishFrame.set_value();
    renderer.join();
    shutdown.join();

    bool laterFrameBlocked = false;
    std::thread lateRenderer([&]() {
        RuntimeLock guard;
        if (sleepPublished.load()) laterFrameBlocked = true;
        else controller.update();
    });
    lateRenderer.join();

    bool allBlack = true;
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
        for (uint32_t color : leds.getStrip(strip)->latchedPixels)
            if (color != 0) allBlack = false;
    return {waitedForFrame, allBlack, laterFrameBlocked};
}
}

#endif
