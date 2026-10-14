#include "SmoothAnimation.h"
#include "../AnimationController.h"
#include "../Topology.h"

namespace {
struct Point { float x, y; };

const Point* normalizedNodes() {
    static Point points[Constants::NUMBER_OF_NODES];
    static bool initialized = false;
    if (!initialized) {
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
        for (int n = 0; n < Constants::NUMBER_OF_NODES; ++n) {
            points[n] = {2.0f * (Topology::nodePositions[n].x - minX) / width - 1.0f,
                         2.0f * (Topology::nodePositions[n].y - minY) / height - 1.0f};
        }
        initialized = true;
    }
    return points;
}

float configNumber(const JsonObject& doc, const char* key, float current,
                   float low, float high) {
    if (!doc[key].is<float>()) return current;
    const float value = doc[key].as<float>();
    if (!std::isfinite(value)) return current;
    return value < low ? low : (value > high ? high : value);
}
}

SmoothAnimation::SmoothAnimation(AnimationController& controller, int defaultPalette)
    : Animation(controller), palette(defaultPalette) {
    const Flow::Color* colors = Flow::paletteStops(palette);
    for (int i = 0; i < Flow::PALETTE_STOPS; ++i) currentPalette[i] = colors[i];
}

void SmoothAnimation::run() {
    lastFrame = static_cast<uint32_t>(millis());
    update();
}

void SmoothAnimation::update() {
    const uint32_t now = static_cast<uint32_t>(millis());
    const double seconds = static_cast<uint32_t>(now - lastFrame) / 1000.0;
    lastFrame = now;
    elapsedSeconds += seconds * speed;

    // Exponential interpolation has the same result at any frame cadence.
    // Palette changes settle gently even while motion is paused (speed == 0).
    const float blend = 1.0f - std::exp(-seconds * 4.0f);
    const Flow::Color* target = Flow::paletteStops(palette);
    for (int i = 0; i < Flow::PALETTE_STOPS; ++i)
        currentPalette[i] = Flow::mix(currentPalette[i], target[i], blend);

    const Point* points = normalizedNodes();
    LedController& leds = controller.getLedController();
    for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; ++segment) {
        const Point top = points[Topology::segmentConnections[segment][0]];
        const Point bottom = points[Topology::segmentConnections[segment][1]];
        for (int led = 0; led < Constants::LEDS_PER_SEGMENT; ++led) {
            const float fraction = Constants::LEDS_PER_SEGMENT > 1
                ? static_cast<float>(led) / (Constants::LEDS_PER_SEGMENT - 1) : 0.5f;
            // Use exact endpoints to keep all branches at a junction identical.
            const Point p = led == 0 && Constants::LEDS_PER_SEGMENT > 1 ? bottom :
                (led == Constants::LEDS_PER_SEGMENT - 1 && Constants::LEDS_PER_SEGMENT > 1 ? top :
                 Point{bottom.x + (top.x - bottom.x) * fraction,
                       bottom.y + (top.y - bottom.y) * fraction});
            const Flow::Color color = Flow::multiply(
                sample(p.x, p.y, static_cast<float>(elapsedSeconds)), brightness / 255.0f);
            leds.setPixelColor(segment, led, Flow::channel(color.r),
                               Flow::channel(color.g), Flow::channel(color.b));
        }
    }
}

void SmoothAnimation::getConfig(JsonObject& doc) {
    Animation::getConfig(doc);
    doc["speed"] = speed;
    doc["scale"] = scale;
    doc["brightness"] = brightness;
    doc["palette"] = palette;
}

void SmoothAnimation::setConfig(const JsonObject& doc) {
    Animation::setConfig(doc);
    speed = configNumber(doc, "speed", speed, 0.0f, 3.0f);
    scale = configNumber(doc, "scale", scale, 0.25f, 3.0f);
    brightness = static_cast<int>(configNumber(doc, "brightness", brightness, 0, 255));
    if (doc["palette"].is<int>()) {
        const int candidate = doc["palette"].as<int>();
        if (candidate >= 0 && candidate < Flow::PALETTE_COUNT) palette = candidate;
    }
}
