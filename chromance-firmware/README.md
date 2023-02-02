How to Setup
---
- Open up [variables.h](src/variables.h)

- Edit the following in `variables.h`
  - Set your LED Type to `#define __LED_TYPE NEOPIXEL` for NEOPIXEL or `#define __LED_TYPE DOTSTAR` for DOTSTAR LEDS

Optionally Edit the Following as needed:
  - `BLUE_STRIP_DATA_PIN`: With the Data Pin you are using for the blue
  - `GREEN_STRIP_DATA_PIN`: With the Data Pin you are using for the green
  - `RED_STRIP_DATA_PIN`: With the Data Pin you are using for the red
  - `BLACK_STRIP_DATA_PIN`: With the Data Pin you are using for the black
  - If using DOTSTAR LEDS
    - `BLUE_STRIP_CLOCK_PIN`: With the Clock Pin you are using for the blue
    - `GREEN_STRIP_CLOCK_PIN`: With the Clock Pin you are using for the red
    - `RED_STRIP_CLOCK_PIN`: With the Clock Pin you are using for the green
    - `BLACK_STRIP_CLOCK_PIN`: With the Clock Pin you are using for the black


How to make an animation
---
To create your own animations you will want to look at the [mapping.h](src/mapping.h) file and the [ripple.cpp](src/ripple.cpp) file to a lesser extent.  This repository contains a [mapping.jpeg](mapping.jpeg) that shows each nodes number and the segment numbers.  You can use this image to make sense of the `nodeConnections`, `segmentConnections`, `borderNodes`, `cubeNodes`, `funNodes`, and `starburstNode` variables in [`mapping.h`](src/mapping.h)