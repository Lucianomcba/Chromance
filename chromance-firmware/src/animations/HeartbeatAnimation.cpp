#include "HeartbeatAnimation.h"
#include "../AnimationController.h"
#include "../Constants.h"
#include "../Topology.h"
#include <cmath>

namespace {
constexpr uint32_t FIRST_END_MS = 280;
constexpr uint32_t SECOND_START_MS = 400;
constexpr uint32_t SECOND_END_MS = 670;

float beat(uint32_t elapsed, uint32_t start, uint32_t holdEnd, uint32_t end)
{
  if (elapsed < start || elapsed >= end) return 0.0f;
  const uint32_t attackEnd = start + 50;
  if (elapsed < attackEnd) return float(elapsed - start) / 50.0f;
  if (elapsed <= holdEnd) return 1.0f;
  return float(end - elapsed) / float(end - holdEnd);
}
}

void HeartbeatAnimation::buildPulseMask()
{
  int minX = Topology::nodePositions[0].x, maxX = minX;
  int minY = Topology::nodePositions[0].y, maxY = minY;
  for (const auto& node : Topology::nodePositions) {
    if (node.x < minX) minX = node.x;
    if (node.x > maxX) maxX = node.x;
    if (node.y < minY) minY = node.y;
    if (node.y > maxY) maxY = node.y;
  }
  const float width = maxX > minX ? maxX - minX : 1;
  const float height = maxY > minY ? maxY - minY : 1;
  const auto center = Topology::nodePositions[Topology::starburstNode];
  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment) {
    const auto top = Topology::nodePositions[Topology::segmentConnections[segment][0]];
    const auto bottom = Topology::nodePositions[Topology::segmentConnections[segment][1]];
    for (int led = 0; led < Constants::LEDS_PER_SEGMENT; ++led) {
      const float f = Constants::LEDS_PER_SEGMENT > 1
          ? float(led) / (Constants::LEDS_PER_SEGMENT - 1) : 0.5f;
      const float x = bottom.x + (top.x - bottom.x) * f;
      const float y = bottom.y + (top.y - bottom.y) * f;
      const float dx = 2.0f * (x - center.x) / width;
      const float dy = 2.0f * (y - center.y) / height;
      float core = 1.0f - std::sqrt(dx * dx + dy * dy) / 0.55f;
      if (core < 0.0f) core = 0.0f;
      // Concentrate the available current at the center. A uniform bright
      // wall clips at the limiter and makes its beats nearly equal in output.
      pulseLevels[segment][led] = static_cast<byte>(std::lround(3.0f + 180.0f * core * core));
    }
  }
  maskReady = true;
}

void HeartbeatAnimation::run()
{
  if (!maskReady) buildPulseMask();
  startTime = static_cast<uint32_t>(millis());
}

bool HeartbeatAnimation::isFinished()
{
  return static_cast<uint32_t>(millis()) - startTime >= 1500U;
}

bool HeartbeatAnimation::canBePreempted()
{
  return static_cast<uint32_t>(millis()) - startTime >= SECOND_END_MS;
}

void HeartbeatAnimation::update()
{
  const uint32_t elapsed = static_cast<uint32_t>(millis()) - startTime;
  const float strength = beat(elapsed, 0, 150, FIRST_END_MS)
      + 0.65f * beat(elapsed, SECOND_START_MS, 520, SECOND_END_MS);
  auto& leds = controller.getLedController();
  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment)
    for (int led = 0; led < Constants::LEDS_PER_SEGMENT; ++led)
      leds.setPixelColor(segment, led,
          static_cast<byte>(std::lround(pulseLevels[segment][led] * strength)), 0, 0);
}

#include "../AnimationRegistry.h"
REGISTER_ANIMATION(HeartbeatAnimation)
