#ifndef FLOW_MATH_H
#define FLOW_MATH_H

#include <cmath>
#include <cstdint>

namespace Flow {
constexpr float TAU = 6.28318530718f;
enum Palette { AURORA, OCEAN, RAINBOW, SUNSET, LAVA, PALETTE_COUNT };
constexpr int PALETTE_STOPS = 6;

struct Color { float r, g, b; };

inline float clamp01(float value) {
    return value < 0.0f ? 0.0f : (value > 1.0f ? 1.0f : value);
}

inline float smoothstep(float value) {
    const float t = clamp01(value);
    return t * t * (3.0f - 2.0f * t);
}

inline Color mix(Color a, Color b, float amount) {
    const float t = clamp01(amount);
    return {a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t,
            a.b + (b.b - a.b) * t};
}

inline Color multiply(Color color, float amount) {
    return {color.r * amount, color.g * amount, color.b * amount};
}

// Keep a masked shape visible as its palette changes. Removing most of the
// common white component retains hue while leaving saturated, colored light.
inline Color vivid(Color color, float peak = 210.0f) {
    const float low = color.r < color.g ? (color.r < color.b ? color.r : color.b)
                                      : (color.g < color.b ? color.g : color.b);
    color.r -= low * 0.85f;
    color.g -= low * 0.85f;
    color.b -= low * 0.85f;
    const float high = color.r > color.g ? (color.r > color.b ? color.r : color.b)
                                       : (color.g > color.b ? color.g : color.b);
    return high > 0.0f ? multiply(color, peak / high) : Color{0.0f, 0.0f, 0.0f};
}

inline uint8_t channel(float value) {
    if (!std::isfinite(value)) return 0;
    return static_cast<uint8_t>(std::round(clamp01(value / 255.0f) * 255.0f));
}

// Original palettes, with equal spacing and a blended last-to-first interval.
inline const Color* paletteStops(int id) {
    static const Color colors[PALETTE_COUNT][PALETTE_STOPS] = {
        {{3, 8, 35}, {0, 82, 72}, {26, 225, 108}, {45, 165, 215}, {96, 38, 190}, {25, 12, 70}},
        {{1, 5, 24}, {0, 28, 75}, {0, 100, 135}, {24, 190, 185}, {115, 222, 216}, {0, 50, 90}},
        {{255, 20, 4}, {255, 150, 0}, {30, 220, 35}, {0, 155, 235}, {75, 35, 235}, {235, 10, 115}},
        {{24, 8, 65}, {92, 20, 120}, {210, 35, 92}, {255, 100, 40}, {245, 185, 75}, {125, 38, 100}},
        {{20, 1, 12}, {100, 3, 18}, {220, 20, 5}, {255, 105, 5}, {255, 195, 35}, {135, 12, 30}}
    };
    return colors[id >= 0 && id < PALETTE_COUNT ? id : AURORA];
}

inline Color samplePalette(const Color* colors, float index) {
    if (!std::isfinite(index)) return colors[0];
    const float position = (index - std::floor(index)) * PALETTE_STOPS;
    const int first = static_cast<int>(position) % PALETTE_STOPS;
    return mix(colors[first], colors[(first + 1) % PALETTE_STOPS],
               smoothstep(position - std::floor(position)));
}

inline Color palette(int id, float index) {
    return samplePalette(paletteStops(id), index);
}
}

#endif
