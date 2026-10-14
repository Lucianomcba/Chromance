#include "Configuration.h"
#include "AnimationController.h"
#include "animations/Animation.h"
#include "Constants.h"

Configuration::Configuration() : sleepEnabled(false), rainbowBrightness(30), autoResumeMinutes(10)
{
}

void Configuration::setSleepEnabled(bool enabled)
{
    if (sleepEnabled != enabled)
    {
        sleepEnabled = enabled;
        save();
    }
}

void Configuration::setRainbowBrightness(int brightness)
{
    if (rainbowBrightness != brightness)
    {
        rainbowBrightness = brightness;
        save();
    }
}

void Configuration::setAutoResumeMinutes(int minutes)
{
    if (minutes < 0 || minutes > MAX_AUTO_RESUME_MINUTES || autoResumeMinutes == minutes) return;
    autoResumeMinutes = minutes;
    if (animationController) animationController->onAutoResumeSettingChanged();
    save();
}

void Configuration::serialize(JsonObject &doc)
{
    doc["sleepEnabled"] = sleepEnabled;
    doc["rainbowBrightness"] = rainbowBrightness;
    doc["autoResumeMinutes"] = autoResumeMinutes;

    if (animationController) {
        JsonArray anims = doc.createNestedArray("animations");
        int count = animationController->getAnimationCount();
        for (int i = 0; i < count; i++) {
            Animation* anim = animationController->getAnimation(i);
            if (anim) {
                JsonObject a = anims.createNestedObject();
                a["id"] = i;
                anim->getConfig(a);
            }
        }
    }
}

void Configuration::deserialize(const JsonObject &doc)
{
    bool changed = false;
    if (doc["sleepEnabled"].is<bool>())
    {
        bool newSleep = doc["sleepEnabled"];
        if (sleepEnabled != newSleep)
        {
            sleepEnabled = newSleep;
            changed = true;
        }
    }
    if (doc["rainbowBrightness"].is<int>())
    {
        int newBright = doc["rainbowBrightness"];
        if (rainbowBrightness != newBright)
        {
            rainbowBrightness = newBright;
            changed = true;
        }
    }

    if (doc["autoResumeMinutes"].is<int>())
    {
        int minutes = doc["autoResumeMinutes"];
        if (minutes >= 0 && minutes <= MAX_AUTO_RESUME_MINUTES && autoResumeMinutes != minutes)
        {
            autoResumeMinutes = minutes;
            changed = true;
            if (animationController) animationController->onAutoResumeSettingChanged();
        }
    }

    if (animationController && doc["animations"].is<JsonArray>()) {
        JsonArray anims = doc["animations"];
        for (JsonObject a : anims) {
            if (a["id"].is<int>()) {
                int id = a["id"];
                Animation* anim = animationController->getAnimation(id);
                if (anim) {
                    bool wasEnabled = anim->isEnabled();
                    anim->setConfig(a);
                    if (anim->isEnabled() != wasEnabled) {
                        changed = true;
                    }
                }
            }
        }
        animationController->recalculateAutoPulseTypes();
    }
    
    if (changed) {
        save();
    }
}

void Configuration::save()
{
    File file = SPIFFS.open(configFilename, FILE_WRITE);
    if (!file)
    {
        Serial.println("Failed to create config file for writing");
        return;
    }

    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    serialize(root);

    if (serializeJson(doc, file) == 0)
    {
        Serial.println("Failed to write config to file");
    }
    file.close();
}

void Configuration::load()
{
    if (!SPIFFS.exists(configFilename))
    {
        Serial.println("Config file does not exist, using defaults.");
        return;
    }

    File file = SPIFFS.open(configFilename, FILE_READ);
    if (!file)
    {
        Serial.println("Failed to open config file for reading");
        return;
    }

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, file);
    if (error)
    {
        Serial.print("Failed to read config file: ");
        Serial.println(error.c_str());
        return;
    }

    // Load values directly without triggering save()
    if (doc["sleepEnabled"].is<bool>())
    {
        sleepEnabled = doc["sleepEnabled"];
    }
    if (doc["rainbowBrightness"].is<int>())
    {
        rainbowBrightness = doc["rainbowBrightness"];
    }

    if (doc["autoResumeMinutes"].is<int>())
    {
        int minutes = doc["autoResumeMinutes"];
        if (minutes >= 0 && minutes <= MAX_AUTO_RESUME_MINUTES)
        {
            autoResumeMinutes = minutes;
            if (animationController) animationController->onAutoResumeSettingChanged();
        }
    }

    if (animationController && doc["animations"].is<JsonArray>()) {
        JsonArray anims = doc["animations"];
        for (JsonObject a : anims) {
            if (a["id"].is<int>()) {
                int id = a["id"];
                Animation* anim = animationController->getAnimation(id);
                if (anim) {
                    anim->setConfig(a);
                }
            }
        }
        animationController->recalculateAutoPulseTypes();
    }
    
    file.close();
    Serial.println("Configuration loaded.");
}