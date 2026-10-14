#ifndef TEST_AUTO_RESUME_H
#define TEST_AUTO_RESUME_H

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>

namespace AutoResumeTest
{
struct SavedMockConfig
{
    bool existed;
    std::string contents;
    SavedMockConfig() : existed(SPIFFS.exists("/config.json"))
    {
        if (existed) {
            std::ifstream file("tmp_spiffs/config.json", std::ios::binary);
            contents.assign(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
        }
    }
    ~SavedMockConfig()
    {
        if (existed) {
            std::ofstream file("tmp_spiffs/config.json", std::ios::binary | std::ios::trunc);
            file << contents;
        } else std::remove("tmp_spiffs/config.json");
    }
};

struct Fixture
{
    LedController leds;
    Configuration config;
    AnimationController controller;

    Fixture() : controller(leds, config)
    {
        reset_mocks();
        leds.begin();
        controller.init();
        config.setAnimationController(&controller);
    }

    int id(const char *name)
    {
        for (int i = 0; i < controller.getAnimationCount(); ++i)
            if (std::strcmp(controller.getAnimation(i)->getName(), name) == 0) return i;
        TEST_ASSERT(false);
        return 255;
    }

    void enableOnly(int id)
    {
        for (int i = 0; i < controller.getAnimationCount(); ++i)
        {
            JsonDocument doc;
            JsonObject obj = doc.to<JsonObject>();
            obj["enabled"] = i == id;
            controller.getAnimation(i)->setConfig(obj);
        }
        controller.recalculateAutoPulseTypes();
    }
};
}

void test_auto_resume()
{
    SPIFFS.begin();
    AutoResumeTest::SavedMockConfig preserveConfig;
    TEST_CASE("Manual mode resumes exactly at its configured deadline and reports state");
    {
        AutoResumeTest::Fixture f;
        TEST_ASSERT(f.config.getAutoResumeMinutes() == 10);
        TEST_ASSERT(!f.controller.isAutoResumePending());
        f.config.setAutoResumeMinutes(1);
        const int center = f.id("Center Pulse");
        f.enableOnly(center);
        f.controller.setAutoSwitching(false);
        f.controller.changeAnimation(center);
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 60);
        // Place the next ordinary finite pulse exactly at the resume boundary.
        ArduinoMock::setMillis(58000);
        f.controller.update();
        ArduinoMock::setMillis(59999);
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 1);
        int resumeCallbacks = 0, runCallbacks = 0;
        f.controller.setStateChangeCallback([&](byte, bool automatic) {
            if (automatic) ++resumeCallbacks;
            ++runCallbacks;
        });
        ArduinoMock::setMillis(60000);
        f.controller.update();
        TEST_ASSERT(f.controller.isAutoSwitching());
        TEST_ASSERT(!f.controller.isAutoResumePending());
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 0);
        // No direct run at expiry: the finite animation runs once through the
        // scheduler, which reports its start after the resume notification.
        TEST_ASSERT(resumeCallbacks == 2 && runCallbacks == 2);
        const int ripplesAfterResume = f.controller.getActiveRippleCount();
        TEST_ASSERT(ripplesAfterResume > 0);
        f.controller.update();
        TEST_ASSERT(resumeCallbacks == 2);
        TEST_ASSERT(f.controller.getActiveRippleCount() == ripplesAfterResume);
    }

    TEST_CASE("Repeated pause and valid manual selections refresh the whole window");
    {
        AutoResumeTest::Fixture f;
        f.config.setAutoResumeMinutes(1);
        f.controller.setAutoSwitching(false);
        ArduinoMock::setMillis(30000);
        f.controller.changeAnimation(f.id("Wave"));
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 60);
        ArduinoMock::setMillis(60000);
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        f.controller.setAutoSwitching(false);
        ArduinoMock::setMillis(90000);
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 30);
        f.controller.changeAnimation(255); // Invalid choices cannot refresh.
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 30);
        ArduinoMock::setMillis(120000);
        f.controller.update();
        TEST_ASSERT(f.controller.isAutoSwitching());
    }

    TEST_CASE("Disabled timeout stays manual; immediate enable cancels a pending timeout");
    {
        AutoResumeTest::Fixture f;
        f.config.setAutoResumeMinutes(0);
        f.controller.setAutoSwitching(false);
        f.controller.changeAnimation(f.id("Wave"));
        ArduinoMock::setMillis(86400000);
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        TEST_ASSERT(!f.controller.isAutoResumePending());
        f.config.setAutoResumeMinutes(1);
        TEST_ASSERT(f.controller.isAutoResumePending());
        f.controller.setAutoSwitching(true);
        TEST_ASSERT(!f.controller.isAutoResumePending());
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 0);
    }

    TEST_CASE("Changing the timeout restarts it from now; disabling cancels it");
    {
        AutoResumeTest::Fixture f;
        f.config.setAutoResumeMinutes(1);
        f.controller.setAutoSwitching(false);
        ArduinoMock::setMillis(30000);
        JsonDocument doc;
        JsonObject obj = doc.to<JsonObject>();
        obj["autoResumeMinutes"] = 2;
        f.config.deserialize(obj);
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 120);
        ArduinoMock::setMillis(60000);
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        f.config.setAutoResumeMinutes(2); // Unchanged save cannot postpone expiry.
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 90);
        ArduinoMock::setMillis(150000);
        f.controller.update();
        TEST_ASSERT(f.controller.isAutoSwitching());
        f.controller.setAutoSwitching(false);
        f.config.setAutoResumeMinutes(0);
        TEST_ASSERT(!f.controller.isAutoResumePending());
        obj["autoResumeMinutes"] = -1;
        f.config.deserialize(obj);
        TEST_ASSERT(f.config.getAutoResumeMinutes() == 0);
        obj["autoResumeMinutes"] = 1441;
        f.config.deserialize(obj);
        TEST_ASSERT(f.config.getAutoResumeMinutes() == 0);
    }

    TEST_CASE("Auto resume uses uint32 elapsed time across millis rollover");
    {
        AutoResumeTest::Fixture f;
        f.config.setAutoResumeMinutes(1);
        const uint32_t started = UINT32_MAX - 29999U;
        ArduinoMock::setMillis(started);
        f.controller.setAutoSwitching(false);
        ArduinoMock::setMillis(uint32_t(started + 59999U));
        f.controller.update();
        TEST_ASSERT(!f.controller.isAutoSwitching());
        TEST_ASSERT(f.controller.getAutoResumeRemainingSeconds() == 1);
        ArduinoMock::setMillis(uint32_t(started + 60000U));
        f.controller.update();
        TEST_ASSERT(f.controller.isAutoSwitching());
    }

    TEST_CASE("Auto resume window survives config save/load and older configs retain the default");
    {
        AutoResumeTest::Fixture f;
        f.config.setAutoResumeMinutes(7);
        Configuration loaded;
        loaded.load();
        TEST_ASSERT(loaded.getAutoResumeMinutes() == 7);
        JsonDocument serialized;
        JsonObject obj = serialized.to<JsonObject>();
        loaded.serialize(obj);
        TEST_ASSERT(obj["autoResumeMinutes"].as<int>() == 7);
        File oldConfig = SPIFFS.open("/config.json", FILE_WRITE);
        const uint8_t older[] = "{\"sleepEnabled\":false,\"rainbowBrightness\":30}";
        oldConfig.write(older, sizeof(older) - 1);
        oldConfig.close();
        Configuration legacy;
        legacy.load();
        TEST_ASSERT(legacy.getAutoResumeMinutes() == 10);
    }
}

#endif
