#ifndef COLORCONVERSION_H
#define COLORCONVERSION_H

#include <cmath>
#include <cstdint>

namespace ColorConversion
{
inline uint16_t hue(float value)
{
    if (!std::isfinite(value))
        return 0;
    float wrapped = std::fmod(value, 65536.0f);
    if (wrapped < 0.0f)
        wrapped += 65536.0f;
    // Adding a tiny negative remainder can round to the upper endpoint.
    if (wrapped >= 65536.0f)
        wrapped = 0.0f;
    return static_cast<uint16_t>(wrapped);
}

inline uint8_t channel(float value)
{
    if (std::isnan(value) || value <= 0.0f)
        return 0;
    if (value >= 255.0f)
        return 255;
    return static_cast<uint8_t>(value);
}
}

#endif
