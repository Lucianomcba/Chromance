#include "LedController.h"
#include "Utils.h"
#if defined(ESP32) && !defined(NATIVE_TEST)
#include <driver/gpio.h>
#include <esp_err.h>

namespace {
const int sleepDataPins[] = {Constants::BLUE_STRIP_DATA_PIN,
    Constants::GREEN_STRIP_DATA_PIN, Constants::RED_STRIP_DATA_PIN,
    Constants::BLACK_STRIP_DATA_PIN
#ifdef USING_DOTSTAR
    , Constants::BLUE_STRIP_CLOCK_PIN, Constants::GREEN_STRIP_CLOCK_PIN,
    Constants::RED_STRIP_CLOCK_PIN, Constants::BLACK_STRIP_CLOCK_PIN
#endif
};

void configureSleepPinLow(int pin)
{
  // Preload LOW before gpio_config enables output and routes SIG_GPIO_OUT_IDX.
  // Do not use gpio_reset_pin: it disables output and enables a pull-up.
  // Retained holds stay enabled while the underlying configuration changes.
  ESP_ERROR_CHECK(gpio_set_level(static_cast<gpio_num_t>(pin), 0));
  ESP_ERROR_CHECK(gpio_set_pull_mode(static_cast<gpio_num_t>(pin), GPIO_PULLDOWN_ONLY));
  gpio_config_t config = {};
  config.pin_bit_mask = 1ULL << pin;
  config.mode = GPIO_MODE_OUTPUT;
  config.pull_up_en = GPIO_PULLUP_DISABLE;
  config.pull_down_en = GPIO_PULLDOWN_ENABLE;
  config.intr_type = GPIO_INTR_DISABLE;
  ESP_ERROR_CHECK(gpio_config(&config));
}
}
#endif

LedController::LedController()
{
  for (int i = 0; i < Constants::NUMBER_OF_STRIPS; i++)
  {
    strips[i] = nullptr;
  }
}

LedController::~LedController()
{
  for (int i = 0; i < Constants::NUMBER_OF_STRIPS; i++)
  {
    if (strips[i] != nullptr)
    {
      delete strips[i];
      strips[i] = nullptr;
    }
  }
}

void LedController::initStrips()
{
  // check if already initialized to prevent double allocation
  if (strips[0] != nullptr)
    return;

#ifdef USING_DOTSTAR
  strips[Constants::BLUE_INDEX] = new Adafruit_DotStar(Constants::BLUE_LENGTH, Constants::BLUE_STRIP_DATA_PIN, Constants::BLUE_STRIP_CLOCK_PIN, DOTSTAR_BRG);
  strips[Constants::GREEN_INDEX] = new Adafruit_DotStar(Constants::GREEN_LENGTH, Constants::GREEN_STRIP_DATA_PIN, Constants::GREEN_STRIP_CLOCK_PIN, DOTSTAR_BRG);
  strips[Constants::RED_INDEX] = new Adafruit_DotStar(Constants::RED_LENGTH, Constants::RED_STRIP_DATA_PIN, Constants::RED_STRIP_CLOCK_PIN, DOTSTAR_BRG);
  strips[Constants::BLACK_INDEX] = new Adafruit_DotStar(Constants::BLACK_LENGTH, Constants::BLACK_STRIP_DATA_PIN, Constants::BLACK_STRIP_CLOCK_PIN, DOTSTAR_BRG);
#else
  strips[Constants::BLUE_INDEX] = new Adafruit_NeoPixel(Constants::BLUE_LENGTH, Constants::BLUE_STRIP_DATA_PIN, NEO_GRB + NEO_KHZ800);
  strips[Constants::GREEN_INDEX] = new Adafruit_NeoPixel(Constants::GREEN_LENGTH, Constants::GREEN_STRIP_DATA_PIN, NEO_GRB + NEO_KHZ800);
  strips[Constants::RED_INDEX] = new Adafruit_NeoPixel(Constants::RED_LENGTH, Constants::RED_STRIP_DATA_PIN, NEO_GRB + NEO_KHZ800);
  strips[Constants::BLACK_INDEX] = new Adafruit_NeoPixel(Constants::BLACK_LENGTH, Constants::BLACK_STRIP_DATA_PIN, NEO_GRB + NEO_KHZ800);
#endif
}

void LedController::begin()
{
#if defined(ESP32) && !defined(NATIVE_TEST)
  // Configure LOW before releasing retained sleep holds to avoid a wake glitch.
  for (int pin : sleepDataPins) configureSleepPinLow(pin);
  gpio_deep_sleep_hold_dis();
  for (int pin : sleepDataPins)
    ESP_ERROR_CHECK(gpio_hold_dis(static_cast<gpio_num_t>(pin)));
#endif
  initStrips();
  clear();

  for (int i = 0; i < Constants::NUMBER_OF_STRIPS; i++)
  {
    strips[i]->begin();
    strips[i]->setBrightness(255);
    strips[i]->show();
    latchedChannelSum[i] = 0;
  }
}

void LedController::prepareForDeepSleep()
{
  clear();
  // The legacy NeoPixel RMT driver returns no delivery status. Repeat a full
  // physical-strip black frame, not just the mapped topology, so a missed or
  // interrupted one-shot transfer does not leave a strip at its last color.
  for (int pass = 0; pass < 3; ++pass)
  {
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
    {
      strips[strip]->clear();
      strips[strip]->show();
      latchedChannelSum[strip] = 0;
    }
    // show() waits for TX; the final strip still needs its reset/latch LOW.
    // 2 ms comfortably exceeds NeoPixel's 300 us library reset interval.
    delay(2);
  }
#if defined(ESP32) && !defined(NATIVE_TEST)
  for (int pin : sleepDataPins)
  {
    configureSleepPinLow(pin);
    ESP_ERROR_CHECK(gpio_hold_en(static_cast<gpio_num_t>(pin)));
  }
  // gpio_hold_en alone does not retain digital pads during ESP32 deep sleep.
  gpio_deep_sleep_hold_en();
#endif
}

void LedController::clear()
{
  memset(ledColors, 0, sizeof(ledColors));
  for (int i = 0; i < Constants::NUMBER_OF_STRIPS; i++)
  {
    strips[i]->clear();
  }
}

void LedController::fade(float decay)
{
  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; segment++)
  {
    for (int led = 0; led < Constants::LEDS_PER_SEGMENT; led++)
    {
      for (int k = 0; k < 3; k++)
      {
        ledColors[segment][led][k] = (byte)(ledColors[segment][led][k] * decay);
      }
    }
  }
}

void LedController::setPixelColor(int segment, int led, byte r, byte g, byte b)
{
  if (segment < 0 || segment >= Constants::NUMBER_OF_SEGMENTS || led < 0 || led >= Constants::LEDS_PER_SEGMENT)
    return;
  ledColors[segment][led][0] = r;
  ledColors[segment][led][1] = g;
  ledColors[segment][led][2] = b;
}

void LedController::addPixelColor(int segment, int led, byte r, byte g, byte b)
{
  if (segment < 0 || segment >= Constants::NUMBER_OF_SEGMENTS || led < 0 || led >= Constants::LEDS_PER_SEGMENT)
    return;

  int newR = ledColors[segment][led][0] + r;
  int newG = ledColors[segment][led][1] + g;
  int newB = ledColors[segment][led][2] + b;

  ledColors[segment][led][0] = (newR > 255) ? 255 : newR;
  ledColors[segment][led][1] = (newG > 255) ? 255 : newG;
  ledColors[segment][led][2] = (newB > 255) ? 255 : newB;
}

void LedController::show()
{
  // Power limiting logic
  constexpr unsigned long fixedCurrent = Constants::CONTROLLER_CURRENT_MA
      + Constants::NUM_OF_PIXELS * Constants::LED_IDLE_CURRENT_MA;
  unsigned long channelSum = 0;
  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; segment++)
  {
    for (int led = 0; led < Constants::LEDS_PER_SEGMENT; led++)
    {
      channelSum += ledColors[segment][led][0];
      channelSum += ledColors[segment][led][1];
      channelSum += ledColors[segment][led][2];
    }
  }

  float scale = 1.0f;
  // Sum before division: truncating every dim channel underestimated load by
  // as much as 1 mA per channel. Reserve the controller's allowance first.
  const float ledCurrent = channelSum * (20.0f / 255.0f);
  const float ledBudget = Constants::MAX_CURRENT_MA > fixedCurrent
      ? Constants::MAX_CURRENT_MA - fixedCurrent : 0;
  if (ledCurrent > ledBudget)
  {
    scale = ledBudget / ledCurrent;
  }

  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; segment++)
  {
    for (int fromBottom = 0; fromBottom < Constants::LEDS_PER_SEGMENT; fromBottom++)
    {
      int stripIdx = Topology::ledAssignments[segment][0];
      int floorIndex = Topology::ledAssignments[segment][2];
      int ceilingIndex = Topology::ledAssignments[segment][1];

      int ledIndex = round(fmap(
          fromBottom,
          0, (Constants::LEDS_PER_SEGMENT - 1),
          floorIndex, ceilingIndex));

      byte r = ledColors[segment][fromBottom][0];
      byte g = ledColors[segment][fromBottom][1];
      byte b = ledColors[segment][fromBottom][2];

      if (scale < 1.0f)
      {
        r = (byte)(r * scale);
        g = (byte)(g * scale);
        b = (byte)(b * scale);
      }

      strips[stripIdx]->setPixelColor(
          ledIndex,
          r,
          g,
          b);
    }
  }

  // Measure the actual mapped bytes after scaling/truncation, rather than the
  // requested frame. Each strip retains its old output until show() latches it.
  unsigned long nextChannelSum[Constants::NUMBER_OF_STRIPS] = {};
  for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
  {
    for (int pixel = 0; pixel < strips[strip]->numPixels(); ++pixel)
    {
      const uint32_t color = strips[strip]->getPixelColor(pixel);
      nextChannelSum[strip] += (color >> 16) & 255;
      nextChannelSum[strip] += (color >> 8) & 255;
      nextChannelSum[strip] += color & 255;
    }
  }
  // Reductions precede increases: every intermediate installation load is
  // bounded by max(previous frame load, next frame load), even when light
  // moves abruptly between strips. Do not clear the installation between frames.
  for (int pass = 0; pass < 2; ++pass)
  {
    for (int strip = 0; strip < Constants::NUMBER_OF_STRIPS; ++strip)
    {
      const bool decreases = nextChannelSum[strip] <= latchedChannelSum[strip];
      if ((pass == 0) != decreases) continue;
      strips[strip]->show();
      latchedChannelSum[strip] = nextChannelSum[strip];
    }
  }
}

void LedController::rainbow(uint16_t first_hue, uint8_t brightness)
{
  for (int segment = 0; segment < Constants::NUMBER_OF_SEGMENTS; segment++)
  {
    for (int led = 0; led < Constants::LEDS_PER_SEGMENT; led++)
    {
      int hue = first_hue + (segment * 65536L / Constants::NUMBER_OF_SEGMENTS);
      uint32_t color = ColorHSV(hue, 255, brightness);
      ledColors[segment][led][0] = (uint8_t)(color >> 16);
      ledColors[segment][led][1] = (uint8_t)(color >> 8);
      ledColors[segment][led][2] = (uint8_t)(color);
    }
  }
}

uint32_t LedController::ColorHSV(uint16_t hue, uint8_t sat, uint8_t val)
{
#ifdef USING_DOTSTAR
  return Adafruit_DotStar::ColorHSV(hue, sat, val);
#else
  return Adafruit_NeoPixel::ColorHSV(hue, sat, val);
#endif
}
