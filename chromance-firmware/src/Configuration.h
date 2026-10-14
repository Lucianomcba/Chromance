#ifndef CONFIGURATION_H
#define CONFIGURATION_H

#include <ArduinoJson.h>
#include <SPIFFS.h>

class AnimationController; // Forward declaration

class Configuration
{
public:
    Configuration();

    void setAnimationController(AnimationController* controller) { this->animationController = controller; }

    bool isSleepEnabled() const { return sleepEnabled; }
    void setSleepEnabled(bool enabled);

    int getRainbowBrightness() const { return rainbowBrightness; }
    void setRainbowBrightness(int brightness);

    // 0 keeps manual mode indefinitely. Changing the window while paused
    // starts a fresh countdown from the setting change.
    static constexpr int MAX_AUTO_RESUME_MINUTES = 1440;
    int getAutoResumeMinutes() const { return autoResumeMinutes; }
    void setAutoResumeMinutes(int minutes);

    void serialize(JsonObject &doc);
    void deserialize(const JsonObject &doc);

    void save();
    void load();

private:
    bool sleepEnabled;
    int rainbowBrightness;
    int autoResumeMinutes;
    const char *configFilename = "/config.json";
    AnimationController* animationController = nullptr;
};

#endif
