#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include "Arduino.h"
#include "AnimationController.h"
#include "LedController.h"
#include "Configuration.h"
#include "mocks/Arduino.h"
#include "mocks/SPIFFS.h"
#include "Topology.h"
#include "animations/Animation.h"

// Mock Definitions
namespace ArduinoMock
{
  unsigned long _millis = 0;
}
HardwareSerial Serial;
SPIFFSFS SPIFFS;

// Simple Test Framework
int tests_passed = 0;
int tests_failed = 0;

#define TEST_ASSERT(condition)                                                   \
  if (!(condition))                                                              \
  {                                                                              \
    std::cout << "FAIL: " << #condition << " at line " << __LINE__ << std::endl; \
    tests_failed++;                                                              \
  }                                                                              \
  else                                                                           \
  {                                                                              \
    tests_passed++;                                                              \
  }

#define TEST_CASE(name) \
  std::cout << "Running Test: " << name << std::endl;

void reset_mocks()
{
  ArduinoMock::_millis = 0;
  // Reset random seed if needed
  std::srand(12345);
}

int animationId(AnimationController& controller, const char* name)
{
  for (int i = 0; i < controller.getAnimationCount(); ++i)
    if (std::string(controller.getAnimation(i)->getName()) == name) return i;
  TEST_ASSERT(false);
  return 255;
}

void test_random_animation()
{
  TEST_CASE("RandomAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Random Pulse"));

  // RandomAnimation::run() immediately starts ripples at a random node.

  // Initial state check - ripples should be active immediately
  int initial_count = animController.getActiveRippleCount();
  std::cout << "RandomAnimation Initial Ripple Count: " << initial_count << std::endl;
  TEST_ASSERT(initial_count > 0);

  // Update a few times
  for (int i = 0; i < 10; i++)
  {
    animController.update();
    ArduinoMock::advanceMillis(100);
  }

  // Should still have some ripples (lifespan is 3000ms, we advanced 1000ms)
  int count = animController.getActiveRippleCount();
  std::cout << "RandomAnimation Ripple Count after 1s: " << count << std::endl;
  TEST_ASSERT(count > 0);
}

void test_cube_animation()
{
  TEST_CASE("CubeAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Cube Pulse"));

  // It should spawn ripples immediately or over time
  // CubeAnimation::run() iterates over nodes and starts ripples

  // Simulate one update
  animController.update();

  int count = animController.getActiveRippleCount();
  std::cout << "CubeAnimation Ripple Count: " << count << std::endl;
  TEST_ASSERT(count > 0);
}

void test_starburst_animation()
{
  TEST_CASE("StarburstAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Starburst"));

  // Starburst spawns multiple ripples from a central node
  int count = animController.getActiveRippleCount();
  std::cout << "StarburstAnimation Ripple Count: " << count << std::endl;
  TEST_ASSERT(count > 0);
}

void test_center_animation()
{
  TEST_CASE("CenterAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Center Pulse"));

  int count = animController.getActiveRippleCount();
  std::cout << "CenterAnimation Ripple Count: " << count << std::endl;
  TEST_ASSERT(count > 0);
}

void test_rainbow_animation()
{
  TEST_CASE("RainbowAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Rainbow"));

  // Force a show to update the strips from the internal buffer
  ledController.show();

  // RainbowAnimation calls ledController.rainbow() directly, it doesn't use ripples.

  int count = animController.getActiveRippleCount();
  std::cout << "RainbowAnimation Ripple Count: " << count << std::endl;
  TEST_ASSERT(count == 0);

  // Verify LEDs are lit by checking the strip directly
  // Using the helper added for NATIVE_TEST
  bool anyLit = false;
  auto strip = ledController.getStrip(0);
  if (strip)
  {
    for (int i = 0; i < strip->numPixels(); i++)
    {
      if (strip->getPixelColor(i) != 0)
      {
        anyLit = true;
        break;
      }
    }
  }

  std::cout << "RainbowAnimation LEDs Lit: " << (anyLit ? "Yes" : "No") << std::endl;
  TEST_ASSERT(anyLit);
}

void test_chase_animation()
{
  TEST_CASE("ChaseAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Chase"));

  // Should have exactly 2 ripples initially (runner and chaser)
  int count = animController.getActiveRippleCount();
  std::cout << "ChaseAnimation Ripple Count: " << count << std::endl;
  TEST_ASSERT(count == 2);

  // Validate behaviors
  bool foundRunner = false;
  bool foundChaser = false;

  for (int i = 0; i < Constants::NUMBER_OF_RIPPLES; i++)
  {
    Ripple &r = animController.getRipple(i);
    if (r.state != STATE_DEAD)
    {
      if (r.getBehavior() == BEHAVIOR_RUNNER)
        foundRunner = true;
      if (r.getBehavior() == BEHAVIOR_CHASE)
        foundChaser = true;
    }
  }

  TEST_ASSERT(foundRunner);
  TEST_ASSERT(foundChaser);
}

void test_heartbeat_animation()
{
  TEST_CASE("Heartbeat has camera-visible double beats after physical power limiting");
  reset_mocks();
  LedController leds;
  Configuration config;
  AnimationController controller(leds, config);
  leds.begin();
  controller.init();
  controller.setAutoSwitching(false);
  controller.startAnimation(animationId(controller, "Heartbeat"));

  auto frame = [&](uint32_t elapsed) {
    ArduinoMock::setMillis(elapsed);
    controller.update();
    int peak = 0;
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
      for (uint32_t color : leds.getStrip(strip)->latchedPixels)
        peak = std::max(peak, int((color >> 16) & 255));
    return peak;
  };
  auto allBlack = [&]() {
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
      for (uint32_t color : leds.getStrip(strip)->latchedPixels)
        if (color != 0) return false;
    return true;
  };

  frame(0);
  TEST_ASSERT(allBlack());
  const int firstPeak = frame(80);
  TEST_ASSERT(firstPeak >= 140);
  TEST_ASSERT(!controller.getAnimation(9)->canBePreempted());
  TEST_ASSERT(frame(140) == firstPeak); // Hold long enough for camera frames.
  frame(320);
  TEST_ASSERT(allBlack()); // Distinct gap between lub and dub.
  const int secondPeak = frame(470);
  TEST_ASSERT(secondPeak >= 80 && secondPeak < firstPeak);
  TEST_ASSERT(frame(510) == secondPeak);
  frame(800);
  TEST_ASSERT(allBlack());
  TEST_ASSERT(controller.getAnimation(9)->canBePreempted());
  frame(1400);
  TEST_ASSERT(allBlack()); // No red floor hiding the pulse.

  // The same waveform must survive the physical device's millis rollover.
  const uint32_t start = UINT32_MAX - 39U;
  ArduinoMock::setMillis(start);
  controller.startAnimation(9);
  ArduinoMock::setMillis(uint32_t(start + 80U));
  controller.update();
  int wrapPeak = 0;
  for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
    for (uint32_t color : leds.getStrip(strip)->latchedPixels)
      wrapPeak = std::max(wrapPeak, int((color >> 16) & 255));
  TEST_ASSERT(wrapPeak == firstPeak);
}

void test_wave_animation()
{
  TEST_CASE("WaveAnimation");
  reset_mocks();

  LedController ledController;
  Configuration configuration;
  AnimationController animController(ledController, configuration);
  ledController.begin();
  animController.init();
  animController.setAutoSwitching(false);

  animController.startAnimation(animationId(animController, "Wave"));

  // Run update
  animController.update();
  ledController.show();

  bool anyLit = false;
  auto strip = ledController.getStrip(0);
  if (strip)
  {
    for (int i = 0; i < strip->numPixels(); i++)
    {
      if (strip->getPixelColor(i) != 0)
      {
        anyLit = true;
        break;
      }
    }
  }
  std::cout << "WaveAnimation LEDs Lit: " << (anyLit ? "Yes" : "No") << std::endl;
  TEST_ASSERT(anyLit);
}

#include "test_flow.h"
#include "test_ripple_flow.h"
#include "test_color_ranges.h"
#include "test_power_limit.h"
#include "test_transitions.h"
#include "test_sleep_shutdown.h"
#include "test_auto_resume.h"
#include "test_sleep_race.h"

int main()
{
  std::cout << "Starting Animation Tests..." << std::endl;

  test_random_animation();
  test_cube_animation();
  test_starburst_animation();
  test_center_animation();
  test_rainbow_animation();
  test_chase_animation();
  test_heartbeat_animation();
  test_wave_animation();
  test_smooth_animations();
  test_ripple_flow();
  test_color_ranges();
  test_power_limit();
  test_transitions();
  test_sleep_shutdown();
  test_auto_resume();
  test_sleep_race();

  std::cout << "\nTest Summary:" << std::endl;
  std::cout << "Passed: " << tests_passed << std::endl;
  std::cout << "Failed: " << tests_failed << std::endl;

  return (tests_failed == 0) ? 0 : 1;
}
