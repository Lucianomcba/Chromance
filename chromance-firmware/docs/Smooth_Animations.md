# Smooth color and motion

Five original effects extend Chromance's existing 24 animations. Each was implemented by a dedicated GPT-6.1 Sol agent at medium reasoning effort, then integrated with shared rendering and configuration.

| ID | Effect | Appearance | Starting palette |
| --- | --- | --- | --- |
| 24 | Aurora | Separated curtains with softly moving rays against a black sky | Aurora |
| 25 | Color Waves | Bending rainbow ribbons separated by dark troughs | Rainbow |
| 26 | Lava Lamp | Four moving blobs that merge and separate in dark fluid | Lava |
| 27 | Noise Drift | Coherent cloud islands surrounded by black space | Sunset |
| 28 | Ocean Waves | Traveling blue-green crests with black troughs | Ocean |

[Open the interactive native preview](animation-preview.html) or [inspect the CLI emulator captures](cli-animation-validation.png). The preview embeds 10 seconds per effect at 20 fps; CLI captures show four moments from separate 12-second runs at normal speed. The interactive preview now uses actual post-limit mock strip output at the modeled 1.5 A budget; CLI captures show colors before current limiting.

## Research

Reviewed October 7, 2026:

- [WLED effects](https://kno.wled.ge/features/effects/) supplies useful visual references: Aurora, Colorwaves, Noise Pal, Pacifica, and the user_fx Lava Lamp. Chromance already has many of the particle and pulse styles in that catalog, so these additions emphasize broad, continuous fields.
- [WLED palettes](https://kno.wled.ge/features/palettes/) separates the color scheme from the effect. These additions follow that useful design: every new effect can use any of the five original Chromance palettes.
- [FastLED Pacifica](https://github.com/FastLED/FastLED/blob/master/examples/Pacifica/Pacifica.ino) demonstrates layered ocean motion and highlights where waves reinforce one another. Ocean Waves applies that concept to Chromance's two-dimensional layout.
- [FastLED Pride2015](https://github.com/FastLED/FastLED/blob/master/examples/Pride2015/Pride2015.ino) provides a reference for flowing color with changing luminance. Color Waves uses independently moving color and brightness fields.

These are new implementations, not ports of upstream effect source. They use the existing Adafruit LED driver without adding FastLED or WLED dependencies.

## Controls

Choose an effect in the web interface and open its settings:

| Control | Range | Behavior |
| --- | --- | --- |
| Speed | 0–3; default 1 | Motion multiplier; 0 pauses motion |
| Pattern scale | 0.25–3; default 1 | Lower values spread changes over more pixels; higher values add tighter detail |
| Brightness | 0–255; default 160 | Effect brightness before the existing hardware current limiter |
| Palette | Aurora, Ocean, Rainbow, Sunset, Lava | Color changes blend over roughly one second, including while motion is paused |

Start with scale 1 and speed 1 for visible shapes and dark gaps. Lower scale values broaden the illuminated regions; speed 0.5 slows their movement. Palette IDs are 0–4 in the order above. Configuration is saved through the existing settings API. Existing animation IDs 0–23 remain unchanged.

## Rendering

`SmoothAnimation` interpolates each pixel's position between its physical endpoint nodes. LED zero remains the floor endpoint, matching the hardware mapping. Every branch at a shared node samples the same color field; patterns do not restart at strip or segment boundaries. The interpolation uses `LEDS_PER_SEGMENT` rather than hardcoded 14-pixel widths.

Palette sampling retains fractional RGB values until final output, eases between color stops, and blends the last stop into the first. Changing palettes interpolates the stops themselves, so it does not require running the effect twice. Motion integrates elapsed milliseconds with 32-bit timer rollover handling. Repeated scheduler checks preserve continuous effects' phase, and LED output is presented after the current frame is rendered.

Legacy traveling ripples now distribute light between neighboring pixels and derive travel distance from elapsed time. Their speed retains a nominal 20 ms frame convention; topology routing and lifetime slowdown are preserved. At segment ends, endpoint brightness is held until the existing node-routing step completes. This improves movement within segments without changing which branches a ripple takes.

Wave, Plasma, Rainbow Pinwheel, and Rainbow Radiate also use bounded color conversions. Negative or overflowing hue values wrap before integer conversion, and Plasma brightness is clamped after evaluating its complete expression.

## Verification

Run `./run_tests.sh` from this directory's parent after PlatformIO has installed ArduinoJson. For an external ArduinoJson installation, pass `ARDUINOJSON_DIR=/path/to/ArduinoJson/src`. The native Makefile tracks header dependencies so layout changes rebuild affected objects.

The native suite checks visible, evolving output; adjacent-frame continuity; shared-node colors; motion at different frame cadences; palette seams and live palette transitions; paused motion; brightness and invalid configuration; fractional ripple motion; expiration and timer rollover. `pio run -e esp-wrover-kit` builds the target firmware without flashing it.

The repaired revision passes 601 native assertions, including under AddressSanitizer and UndefinedBehaviorSanitizer. These include transition cleanup, shared rendering locks, current at every intermediate strip latch, and a minute of each effect retaining dark gaps and visible shapes. All five new effects and Starburst were initially run for 12 seconds each in the CLI emulator; Aurora was brightened after reviewing those captures.

After the final contrast repair, all five new effects were run again for six seconds each at normal speed: 91 sampled terminal frames per effect, with all 90 transitions changing. [Recovery CLI captures](cli-recovery-validation.png) show representative frames; [measurements](cli-recovery-validation.json) record continuity. Visual review found coherent moving fields without global flashes or frozen output. The terminal merges physical pixels and suppresses very dim cells, so these captures are a rendering check rather than a hardware timing test.

Host tests establish numerical continuity, not the appearance of a particular diffuser or LED strip. Physical frame rate and low-brightness appearance still need observation on the wall; the 8-bit LED output and existing power limiter remain the final display constraints.

## Hardware incident and recovery

The first OTA image transferred and passed brief HTTP/WebSocket checks, but the user subsequently reported random flashes, freezing, and crashes. Those initial checks did not establish hardware stability. That image used an unpinned platform development checkout (`e51e90a`, reporting 7.1.3) with Arduino 3.3.12. Its SHA-256 was `431474631dbd53dd5491dd8a999ddfbbb3d4c396f925c2e3c73d4ad1bd31c4ee`.

The repair serializes rendering, animation changes, configuration writes, and frame snapshots through one recursive lock. WebSocket sends occur outside that lock. Changing effects stops the prior effect, clears its ripple pool and pixels, and resets its runner. The render loop yields every frame, OTA waits for an in-flight frame, and the current limiter sums fractional LED current before rounding and reserves 200 mA for the controller. Status now includes uptime, free heap, reset reason, and Arduino/IDF versions. These address concrete defects and plausible causes; no serial crash trace was available to identify one definitive cause.

Recovery uses `esp-wrover-kit` with Espressif32 6.9.0 and Arduino 2.0.17 / IDF 4.4.7. Its image uses 61,180 bytes RAM and 1,376,033 bytes application flash. SHA-256: `68172958294a931002cf4a42b75854404238221c667dc894789cd08e4a81887e`. OTA installation was confirmed by revision `smooth-recovery-1` and runtime version diagnostics. The user confirmed the physical lights looked stable. Recovery images boot into the user's manual Fireflies selection (ID 6), with automatic switching off and the saved sleep setting preserved.

The comparison environment `esp-wrover-kit-7_1_3` pins the [official v7.1.3 release tag](https://github.com/platformio/platform-espressif32/releases/tag/v7.1.3), commit `ac95e7aa3b0e5f309359a028706f809f03ffa612`. Its [manifest](https://raw.githubusercontent.com/platformio/platform-espressif32/v7.1.3/platform.json) still uses Arduino 2.0.17. An unqualified `espressif32 @ 7.1.3` matched the cached development checkout locally, so the explicit tag matters. Build with `pio run -e esp-wrover-kit-7_1_3`; add `-t upload` for OTA. Keep the 6.9.0 image as a rollback while assessing this trial.

When downgrading from Arduino 3.3.12, use that newer framework's `tools/espota.py` to upload the saved image: its uploader supports both new SHA256 and legacy MD5 authentication. Arduino 2.0.17's older uploader cannot authenticate with the newer running server. After the downgrade, the ordinary PlatformIO uploader works again. The 7.1.3 build also requires the Python `intelhex` package used by esptool 4.11.


### Power and contrast follow-up

The first recovery removed the reported flashing, but extended observation caught autonomous brownout resets (`resetReason: 9`), including while a legacy effect was selected. The user identified a shared Mean Well LRS-100-5 supply rated 5 V / 18 A; that rating alone does not establish voltage at the controller under changing load. The earlier short stability confirmation was therefore insufficient to call the whole issue resolved.

Revision `smooth-recovery-2` lowers the modeled total budget to 1,500 mA, provisionally allocating 350 mA to the controller and 1 mA per powered LED (560 mA total), leaving 590 mA for RGB output. These are conservative estimates, not electrical measurements. Each strip retains its preceding frame until its next update; the firmware now transmits strips whose load decreases before those whose load increases. This prevents intermediate combinations of old and new frames from exceeding either frame's modeled total load. The brownout detector remains enabled.

The visual revision removes background glow and long bright tails. Aurora has separated curtains, Color Waves has distinct ribbons, Lava Lamp has black space between blobs, Noise Drift has cloud islands, and Ocean Waves has black troughs. Aurora/Lava colors stay saturated and visible through dark palette phases. The minute-long regression check requires at least 25% of pixels to be completely black and visible shapes to remain present at default settings. This addresses the user's observation that an almost fully lit wall obscured the animation shapes.

[Physical-output measurements](physical-output-validation.csv) sample 201 frames per effect over ten seconds from the mock strips after limiting. All individual strip update steps stayed within the modeled 1.5 A budget. The interactive preview embeds those limited frames; neither the native preview nor its illustrative halos can reproduce the actual wall's exposure, diffuser, supply voltage, or wiring.

The new 6.9.0 image uses 61,196 bytes RAM and 1,376,553 bytes application flash. SHA-256: `499c569e73d62c0eb433cad1b11de92f81d4896a6efc37a2b2cfc82fcc2bec35`. The device checks below assess physical operation separately from native rendering checks.


The 6.9.0 revision-2 OTA completed successfully, and a 127.6-second device check observed 1,005 LED stream frames (998 distinct), all five new effects, continuing uptime, and a minimum sampled free heap of 148,480 bytes. The user reported that the contrast looked great. The user also observed a 3–4-second stutter during the diagnostic's three-second status polling; it stopped when that traffic stopped. Revision `smooth-recovery-3` addresses the matching lock contention by copying status fields briefly under the render mutex and constructing/serializing JSON afterward.

The official 7.1.3 revision-3 build uses 61,196 bytes RAM and 1,376,973 bytes application flash. Its framework resolves to Arduino 2.0.17, with the release platform commit `ac95e7a`. SHA-256: `fd82c620404e74bd45d5e6b43433116245a6205c1c0e37d3c584463ed40843f0`.


The official 7.1.3 revision-3 image completed a 120.9-second device check without a reset: 931 streamed frames (924 distinct), minimum sampled free heap 146,472 bytes, Arduino 2.0.17 / IDF 4.4.7, and manual Ocean Waves retained. The check included the three-second status polling associated with the earlier reported stutter; physical motion feedback is separate from these uptime/network measurements.

Revision `smooth-recovery-4` adds alphabetical sorting to both the main animation list and the global settings list. Sorting operates on a copied presentation array; all 29 animation IDs and stored selections are preserved. It otherwise retains revision-3 behavior. Build usage: 61,196 bytes RAM and 1,377,181 bytes application flash. SHA-256: `b5a88d9bdc910265d70d76e6cdb66da72cf15ca8ac82e1c747d73abd310d57aa`.

Final revision-4 OTA completed successfully at approximately `2026-10-08T00:23:56Z`. The device served JavaScript byte-for-byte identical to the validated alphabetically sorted UI. A 33.2-second post-reboot check observed 259 frames (256 distinct), continuing uptime, and no reset. Manual Ocean Waves (ID 28), all 29 effects, and the sleep setting were preserved. Diagnostic polling and the verification WebSocket were stopped after the check. The lower-load 6.9.0 revision-2 artifact remains available as the rollback image.


## Sleep and auto-resume

Implemented and deployed October 14, 2026 as `sleep-auto-resume-1` on official Espressif32 7.1.3 / Arduino 2.0.17. The normal 22:00–08:00 schedule remains in place. The temporary recovery flag is no longer enabled: boot and timer wake begin normal automatic switching.

The device previously reported a deep-sleep wake while the user observed that some LEDs remained lit overnight. The prior shutdown sent one black frame with Wi-Fi active, from Core0, and did not retain LOW on LED data pads. The renderer already used a shared lock, so an unguarded software redraw race was not established as the original cause. Plausible causes include an incomplete final transfer or pad/signal transitions after the powered LEDs latch their last values.

Shutdown now publishes a request behind the render barrier. Core1 stops Wi-Fi, clears all physical strip buffers, sends three black frames with 2 ms latch delays, and holds data pins LOW through sleep. Wake configures LOW before releasing holds. Pin configuration preloads LOW and disables pull-up instead of resetting to an input/pull-up state. This follows [Espressif's GPIO hold guidance](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-reference/peripherals/gpio.html#_CPPv412gpio_hold_en10gpio_num_t). [Espressif's RMT FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/peripherals/rmt.html) documents Wi-Fi interrupt interference as a possible source of RGB data corruption; that supports the hypothesis, but does not prove which electrical failure occurred here.

The native fault test seeds every physical LED and simulates a lost first black transmission. The old one-shot sequence leaves pixels lit; repeated blackout clears them. `./emulator --validate-sleep` also runs a controlled concurrent frame/shutdown test using the real controller, blackout method, and shared RuntimeLock. Its unguarded control deliberately finishes a frame after blackout and relights pixels. The guarded case waits for the in-flight frame, ends with all physical mock pixels black, and blocks a later frame. The host lifecycle gate models main.cpp's sleep-request state; it does not emulate RMT, Wi-Fi, GPIO retention, or the actual sleep instruction.

The full native suite passes 2,917 assertions, including under AddressSanitizer and UndefinedBehaviorSanitizer. The concurrency case repeats ten times. A normal six-second Color Waves CLI run also produced 91 sampled frames through 5,940 ms.

Global settings now include `autoResumeMinutes`: default 10, integer range 0–1440, with 0 leaving manual mode indefinitely. Manual selection or pausing resets the countdown. Changing the configured duration while paused starts a fresh countdown; enabling automatic switching cancels it. Expiry uses the existing scheduler. The timeout is saved to SPIFFS; pending countdowns reset on reboot, which starts automatic mode. Status exposes `autoResumePending` and `autoResumeRemainingSeconds`.

Live validation temporarily selected a one-minute window and manual Color Waves. It remained manual through the last sample at 51.5 seconds, then automatic mode was observed at 61.8 seconds with no pending countdown. The saved setting was restored to 10 minutes afterward.

`POST /api/sleep/test` queues one fixed validation nap: a 1-second response grace, normal blackout, a 5-second dark observation pause, and 30 seconds of deep sleep. It rejects an active OTA update or another queued sleep. It does not alter the overnight preference. Two device cycles went offline and returned after about 40.8 seconds; both reported reset reason 8 and timer wake cause 4, with automatic switching and the 10-minute timeout restored. The first physical cycle was not observed by the user. On the coordinated repeat, the user reported all LEDs dark. The five-second pause distinguishes a failed black transfer from a change at sleep entry; it is only used by the explicit validation endpoint, not scheduled nightly sleep.

Build usage: 61,220 bytes RAM and 1,381,525 bytes application flash. Deployed image SHA-256: `cf839b266eb3af8e95e7fae6a054c1fb251dbbe0daf0b3bbcdbdc4161ae0b2de`. [Device evidence](sleep-auto-resume-validation.json) records both cycles and the live timeout samples. Native tests prove software invariants; the physical observation and reported timer wake provide the hardware evidence.
