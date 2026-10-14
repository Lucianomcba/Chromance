/*
   Chromance wall hexagon source (emotion controlled w/ EmotiBit)
   Partially cribbed from the DotStar example
   I smooshed in the ESP32 BasicOTA sketch, too

   (C) Voidstar Lab 2021
*/

#include <Arduino.h>
#include <WiFi.h>
#include "time.h"
#include <ESPmDNS.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include <WiFiManager.h> //https://github.com/tzapu/WiFiManager WiFi Configuration Magic
#include <SPIFFS.h>

#include "Constants.h"
#include "LedController.h"
#include "AnimationController.h"
#include "ChromanceWebServer.h"
#include "Configuration.h"
#include "RuntimeLock.h"
#include "SleepControl.h"
#include <atomic>

// Globals
Configuration configuration;
LedController ledController;
AnimationController animationController(ledController, configuration);
ChromanceWebServer webServer(animationController, configuration);

const char *ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -18000;       // EST is UTC-5 (-5 * 3600)
const int daylightOffset_sec = 3600;     // Daylight saving offset is 1 hour
const uint64_t uS_TO_S_FACTOR = 1000000; /* Conversion factor for micro seconds to seconds */

// Task for running on Core 0
TaskHandle_t Core0TaskHandle;

// Semaphore for protecting shared variables (activeOTAUpdate, animating)
std::atomic<bool> activeOTAUpdate{false};
std::atomic<bool> animating{true};
// Core0 requests sleep; the rendering core owns every LED transmission.
// Access under RuntimeLock so publishing also waits for an in-flight frame.
bool sleepRequested = false;
uint64_t requestedSleepUs = 0;
bool requestedSleepValidation = false;
uint32_t sleepRequestStartedAt = 0;

bool requestDeepSleepValidation()
{
  RuntimeLock guard;
  if (sleepRequested || activeOTAUpdate.load()) return false;
  requestedSleepUs = 30ULL * uS_TO_S_FACTOR;
  requestedSleepValidation = true;
  sleepRequestStartedAt = static_cast<uint32_t>(millis());
  sleepRequested = true;
  animating.store(false);
  return true;
}

// Function declarations
void connectToWiFi();
void setupOTA(void);

// Thread for running on opposite thread as loop
void Core0Task(void *pvParameters)
{
  Serial.print("Task1 running on core ");
  Serial.println(xPortGetCoreID());

  for (;;)
  {
    bool stopNetworkWork;
    {
      RuntimeLock guard;
      stopNetworkWork = sleepRequested;
      // Publish OTA's onStart flag under the same barrier as sleep requests.
      // Otherwise OTA could start between checking the flag and handle().
      if (!stopNetworkWork) ArduinoOTA.handle();
    }
    // Release the shared lock before suspending this task.
    if (stopNetworkWork) vTaskSuspend(nullptr);
    webServer.broadcastLedData();

    static unsigned long lastTimeCheck = 0;
    // Check the time every 2 seconds
    if (millis() - lastTimeCheck > 2000)
    {
      lastTimeCheck = millis();
      struct tm timeinfo;
      if (!getLocalTime(&timeinfo, 10))
      {
        Serial.println("Failed to obtain time");
        delay(100);
        continue;
      }

      // Sleep between 10pm and 8am
      if (timeinfo.tm_hour >= 22 || timeinfo.tm_hour < 8)
      {
        bool sleepEnabled;
        {
          RuntimeLock guard;
          sleepEnabled = configuration.isSleepEnabled();
        }
        if (!sleepEnabled)
        {
          continue;
        }

        // Calculate sleep duration to wake up at 8am
        time_t now = time(nullptr);
        struct tm wakeup_time_info = timeinfo;
        wakeup_time_info.tm_hour = 8;
        wakeup_time_info.tm_min = 0;
        wakeup_time_info.tm_sec = 0;

        // If current time is past 8am, the wakeup is tomorrow
        if (timeinfo.tm_hour >= 8)
        {
          wakeup_time_info.tm_mday += 1;
        }

        time_t wakeup_t = mktime(&wakeup_time_info);
        double sleep_seconds = difftime(wakeup_t, now);
        uint64_t sleep_us = (uint64_t)(sleep_seconds * uS_TO_S_FACTOR);

        Serial.printf("Current time: %s", asctime(&timeinfo));
        Serial.printf("Wakeup time:  %s", asctime(&wakeup_time_info));
        Serial.printf("Going to sleep for %.f seconds.\n", sleep_seconds);

        {
          RuntimeLock guard;
          // Recheck after acquiring the render barrier; do not sleep mid OTA.
          if (sleepRequested || !configuration.isSleepEnabled() || activeOTAUpdate.load()) continue;
          requestedSleepUs = sleep_us;
          requestedSleepValidation = false;
          sleepRequested = true;
          animating.store(false);
        }
      }
    }

    delay(100);
  }
}

void setupOTA()
{
  // Start OTA server.
  ArduinoOTA.setHostname(Constants::HOSTNAME);
  ArduinoOTA.setPassword("esp32password");

  ArduinoOTA
      .onStart([]()
               {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH)
      type = "sketch";
    else // U_SPIFFS
      type = "filesystem";

    // Protect shared variable access with mutex
    activeOTAUpdate.store(true);
    {
      // Wait for any in-flight frame to finish before OTA starts writing.
      RuntimeLock guard;
      animating.store(false);
    }
    // NOTE: if updating SPIFFS this would be the place to unmount SPIFFS using SPIFFS.end()
    Serial.println("Start updating " + type); });
  ArduinoOTA.onEnd([]()
                   { Serial.println("\nEnd"); });
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total)
                        { Serial.printf("Progress: %u%%\r", (progress / (total / 100))); });
  ArduinoOTA.onError([](ota_error_t error)
                     {
                      // Protect shared variable access with mutex
                      activeOTAUpdate = false;
                      Serial.printf("Error[%u]: ", error);
                      if (error == OTA_AUTH_ERROR)
                        Serial.println("Auth Failed");
                      else if (error == OTA_BEGIN_ERROR)
                        Serial.println("Begin Failed");
                      else if (error == OTA_CONNECT_ERROR)
                        Serial.println("Connect Failed");
                      else if (error == OTA_RECEIVE_ERROR)
                        Serial.println("Receive Failed");
                      else if (error == OTA_END_ERROR)
                        Serial.println("End Failed"); });

  ArduinoOTA.setMdnsEnabled(true);
  ArduinoOTA.setRebootOnSuccess(true);
  delay(500);
  ArduinoOTA.begin();

  // loop and setup are pinned to core 1
  xTaskCreatePinnedToCore(
      Core0Task,        /* Task function. */
      "Core0Task",      /* name of task. */
      16384,            /* Stack size of task */
      NULL,             /* parameter of the task */
      1,                /* priority of the task */
      &Core0TaskHandle, /* Task handle to keep track of created task */
      0);               /* pin task to core 0 */
}

void connectToWiFi()
{
  WiFi.mode(WIFI_STA);
  // Check if already connected (simple check, though WiFiManager handles auto-reconnect)
  if (WiFi.status() == WL_CONNECTED)
    return;

  WiFiManager wifiManager;
  wifiManager.setWiFiAutoReconnect(true);
  wifiManager.autoConnect(Constants::HOSTNAME);
  Serial.printf("WiFi connected! IP address: %s\n", WiFi.localIP().toString().c_str());
}

void setup()
{
  Serial.begin(115200);
  Serial.println("*** LET'S GOOOOO ***");

  // Mount SPIFFS
  if (!SPIFFS.begin(true))
  {
    Serial.println("An Error has occurred while mounting SPIFFS");
  }

  // Create mutex semaphore for protecting shared animation state
  ledController.begin();

  connectToWiFi();
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  animationController.init();

  // Load configuration from flash
  configuration.setAnimationController(&animationController);
  configuration.load();

#ifdef CHROMANCE_RECOVERY_MODE
  // Recovery images boot into the user's manual selection for observation.
  animationController.setAutoSwitching(false);
  animationController.startAnimation(6); // Fireflies: stable legacy ID.
#endif

  // Check wakeup cause
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_TIMER)
  {
    Serial.println("Woke up from deep sleep (Timer)!");
    // Preserve the saved sleep preference, including after a validation nap.
  }
  else if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0)
  {
    Serial.println("Woke up from button press!");
    // Disable sleep
    configuration.setSleepEnabled(false);
  }

  webServer.begin();

  setupOTA();
}

void loop()
{
  const unsigned long started = millis();
  uint64_t sleepUs = 0;
  bool validationSleep = false;
  uint32_t requestStartedAt = 0;
  {
    RuntimeLock guard;
    // Recheck after acquiring the same lock OTA uses as its render barrier.
    if (sleepRequested)
    {
      animating.store(false);
      sleepUs = requestedSleepUs;
      validationSleep = requestedSleepValidation;
      requestStartedAt = sleepRequestStartedAt;
    }
    else if (activeOTAUpdate.load())
      animating.store(false);
    else
    {
      animating.store(true);
      animationController.update();
    }
  }
  if (sleepUs > 0)
  {
    // Let the POST response leave AsyncTCP before shutting WiFi down. Rendering
    // has already stopped; elapsed subtraction also works across millis wrap.
    if (validationSleep)
      while (static_cast<uint32_t>(millis()) - requestStartedAt < 1000U)
        delay(10);
    esp_sleep_enable_timer_wakeup(sleepUs);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, 0);
    // Stop WiFi before the last RMT transfers, on the usual rendering core.
    // Do not hold RuntimeLock while stopping WiFi: callbacks may need it.
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    {
      // Prevent any remaining asynchronous controller/config callbacks from
      // touching buffers during blackout or the transition into sleep.
      RuntimeLock guard;
      ledController.prepareForDeepSleep();
      Serial.printf("Sleep blackout complete on core %d; data held LOW.\n", xPortGetCoreID());
      Serial.flush();
      // Fixed validation pause distinguishes failed blackout from entry noise.
      // Scheduled overnight sleep retains its normal immediate transition.
      if (validationSleep) delay(5000);
      esp_deep_sleep_start();
    }
  }
  const unsigned long frameDuration = millis() - started;
  // Bound refresh rate and always let the idle/network tasks run.
  delay(frameDuration < 20 ? 20 - frameDuration : 1);
}
