#include "ChromanceWebServer.h"
#include "Constants.h"
#include "animations/Animation.h"
#include "WebAssets.h"
#include "Topology.h"
#include "RuntimeLock.h"
#include "SleepControl.h"
#include <array>
#ifdef ESP32
#include <esp_system.h>
#include <esp_sleep.h>
#include <esp_arduino_version.h>
#endif

ChromanceWebServer::ChromanceWebServer(AnimationController &animationController, Configuration &configuration)
    : server(80), ws("/ws"), animationController(animationController), configuration(configuration)
{
}

void ChromanceWebServer::begin()
{
    setupRoutes();
    {
        RuntimeLock guard;
        animationController.setStateChangeCallback([this](byte, bool)
                                                   { pendingStatus.store(true); });
    }
    server.begin();
}

void ChromanceWebServer::setupRoutes()
{
    // WebSocket
    ws.onEvent([this](AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len)
               { this->onEvent(server, client, type, arg, data, len); });
    server.addHandler(&ws);

    // Serve Static HTML
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request)
              { request->send(200, "text/html; charset=utf-8", index_html); });

    server.on("/style.css", HTTP_GET, [](AsyncWebServerRequest *request)
              { request->send(200, "text/css", style_css); });

    server.on("/script.js", HTTP_GET, [](AsyncWebServerRequest *request)
              { request->send(200, "application/javascript", script_js); });

    // API Status
    server.on("/api/status", HTTP_GET, [this](AsyncWebServerRequest *request)
              {
        AsyncResponseStream *response = request->beginResponseStream("application/json");
        response->print(getStatusJson());
        request->send(response); });

    // Explicit, bounded validation of the normal hardware shutdown path.
    // Network response grace and a dark pause precede the 30-second sleep.
    server.on("/api/sleep/test", HTTP_POST, [](AsyncWebServerRequest *request) {
        if (!requestDeepSleepValidation()) {
            request->send(409, "application/json", "{\"status\":\"busy\"}");
            return;
        }
        request->send(200, "application/json",
            "{\"status\":\"ok\",\"sleepSeconds\":30,\"blackoutPauseSeconds\":5}");
    });

    // Parse bounded JSON bodies: never read beyond the supplied async chunk.
    server.on("/api/animation", HTTP_POST, [](AsyncWebServerRequest *) {}, NULL,
        [this](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
            if (index != 0) return; // A rejected fragmented body gets one response.
            JsonDocument doc;
            if (len != total || deserializeJson(doc, data, len) || !doc["id"].is<int>()) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing or invalid id\"}");
                return;
            }
            bool validId;
            {
                RuntimeLock guard;
                const int id = doc["id"].as<int>();
                validId = id >= 0 && id < animationController.getAnimationCount();
                if (validId) {
                    animationController.setAutoSwitching(false);
                    animationController.changeAnimation(id);
                }
            }
            request->send(validId ? 200 : 400, "application/json",
                validId ? "{\"status\":\"ok\"}" : "{\"status\":\"error\",\"message\":\"Invalid animation id\"}");
        });

    server.on("/api/autoswitch", HTTP_POST, [](AsyncWebServerRequest *) {}, NULL,
        [this](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
            if (index != 0) return; // A rejected fragmented body gets one response.
            JsonDocument doc;
            if (len != total || deserializeJson(doc, data, len) || !doc["enabled"].is<bool>()) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing enabled\"}");
                return;
            }
            {
                RuntimeLock guard;
                animationController.setAutoSwitching(doc["enabled"].as<bool>());
            }
            request->send(200, "application/json", "{\"status\":\"ok\"}");
        });

    server.on("/api/sleep", HTTP_POST, [](AsyncWebServerRequest *) {}, NULL,
        [this](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
            if (index != 0) return; // A rejected fragmented body gets one response.
            JsonDocument doc;
            if (len != total || deserializeJson(doc, data, len) || !doc["enabled"].is<bool>()) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing enabled\"}");
                return;
            }
            {
                RuntimeLock guard;
                configuration.setSleepEnabled(doc["enabled"].as<bool>());
                pendingStatus.store(true);
            }
            request->send(200, "application/json", "{\"status\":\"ok\"}");
        });

    server.on("/api/config/global", HTTP_GET, [this](AsyncWebServerRequest *request) {
        JsonDocument doc;
        {
            RuntimeLock guard;
            JsonObject obj = doc.to<JsonObject>();
            configuration.serialize(obj);
            JsonArray anims = obj["animations"].to<JsonArray>();
            for (int i = 0; i < animationController.getAnimationCount(); ++i) {
                Animation *anim = animationController.getAnimation(i);
                if (anim) {
                    JsonObject item = anims.add<JsonObject>();
                    item["id"] = i;
                    item["name"] = anim->getName();
                    item["enabled"] = anim->isEnabled();
                }
            }
        }
        String body;
        serializeJson(doc, body);
        request->send(200, "application/json", body);
    });

    server.on("/api/config/global", HTTP_POST, [](AsyncWebServerRequest *) {}, NULL,
        [this](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
            if (index != 0) return; // A rejected fragmented body gets one response.
            JsonDocument doc;
            if (len != total || deserializeJson(doc, data, len)) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
                return;
            }
            if (doc.containsKey("autoResumeMinutes") &&
                (!doc["autoResumeMinutes"].is<int>() || doc["autoResumeMinutes"].as<int>() < 0 ||
                 doc["autoResumeMinutes"].as<int>() > Configuration::MAX_AUTO_RESUME_MINUTES)) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"autoResumeMinutes must be 0-1440\"}");
                return;
            }
            {
                RuntimeLock guard;
                configuration.deserialize(doc.as<JsonObject>());
                pendingStatus.store(true);
            }
            request->send(200, "application/json", "{\"status\":\"ok\"}");
        });

    server.on("/api/config", HTTP_GET, [this](AsyncWebServerRequest *request) {
        if (!request->hasParam("id")) {
            request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing id\"}");
            return;
        }
        JsonDocument doc;
        bool found = false;
        {
            RuntimeLock guard;
            Animation *anim = animationController.getAnimation(request->getParam("id")->value().toInt());
            if (anim) {
                JsonObject obj = doc.to<JsonObject>();
                anim->getConfig(obj);
                found = true;
            }
        }
        String body;
        if (found) serializeJson(doc, body);
        else body = "{\"status\":\"error\",\"message\":\"Animation not found\"}";
        request->send(found ? 200 : 404, "application/json", body);
    });

    server.on("/api/config", HTTP_POST, [](AsyncWebServerRequest *) {}, NULL,
        [this](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
            if (index != 0) return; // A rejected fragmented body gets one response.
            if (!request->hasParam("id")) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing id\"}");
                return;
            }
            JsonDocument doc;
            if (len != total || deserializeJson(doc, data, len)) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
                return;
            }
            bool found = false;
            {
                RuntimeLock guard;
                Animation *anim = animationController.getAnimation(request->getParam("id")->value().toInt());
                if (anim) {
                    anim->setConfig(doc.as<JsonObject>());
                    animationController.recalculateAutoPulseTypes();
                    configuration.save();
                    pendingStatus.store(true);
                    found = true;
                }
            }
            request->send(found ? 200 : 404, "application/json",
                found ? "{\"status\":\"ok\"}" : "{\"status\":\"error\",\"message\":\"Animation not found\"}");
        });
}

void ChromanceWebServer::onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len)
{
    if (type == WS_EVT_CONNECT)
    {
        Serial.printf("WebSocket client #%u connected from %s\n", client->id(), client->remoteIP().toString().c_str());

        // Send configuration first
        client->text(getEmulatorConfigJson());

        // Then send status
        client->text(getStatusJson());

        // Default to enabled for backward compatibility
        RuntimeLock guard;
        emulatorClients.push_back(client->id());
        clientsNeedingFullFrame.insert(client->id());
    }
    else if (type == WS_EVT_DISCONNECT)
    {
        Serial.printf("WebSocket client #%u disconnected\n", client->id());
        RuntimeLock guard;
        auto it = std::find(emulatorClients.begin(), emulatorClients.end(), client->id());
        if (it != emulatorClients.end())
        {
            emulatorClients.erase(it);
        }
        clientsNeedingFullFrame.erase(client->id());
    }
    else if (type == WS_EVT_DATA)
    {
        handleWebSocketMessage(client, arg, data, len);
    }
}

void ChromanceWebServer::handleWebSocketMessage(AsyncWebSocketClient *client, void *arg, uint8_t *data, size_t len)
{
    AwsFrameInfo *info = (AwsFrameInfo *)arg;
    if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT)
    {
        JsonDocument doc;
        DeserializationError error = deserializeJson(doc, data, len);
        if (error)
        {
            return;
        }

        if (doc["type"] == "ping")
        {
            client->text("{\"type\":\"pong\"}");
            return;
        }

        if (doc["emulator"].is<bool>())
        {
            RuntimeLock guard;
            bool enabled = doc["emulator"];
            auto it = std::find(emulatorClients.begin(), emulatorClients.end(), client->id());
            if (enabled)
            {
                if (it == emulatorClients.end())
                {
                    emulatorClients.push_back(client->id());
                    clientsNeedingFullFrame.insert(client->id());
                }
            }
            else
            {
                if (it != emulatorClients.end())
                {
                    emulatorClients.erase(it);
                }
            }
        }
    }
}

void ChromanceWebServer::broadcastStatus()
{
    pendingStatus.store(true);
}

void ChromanceWebServer::broadcastLedData()
{
    // Controller callbacks run inside the render mutex. Network work is
    // deferred here so AsyncTCP can never wait on a mutex held by its sender.
    if (pendingStatus.exchange(false)) ws.textAll(getStatusJson());
    if (ws.count() == 0) return;
    static unsigned long lastUpdate = 0;
    if (millis() - lastUpdate < 33) return;
    lastUpdate = millis();

    constexpr size_t bufferSize = Constants::NUMBER_OF_SEGMENTS * Constants::LEDS_PER_SEGMENT * 3;
    std::array<uint8_t, bufferSize> frame;
    std::vector<uint32_t> recipients;
    std::set<uint32_t> fullRecipients;
    {
        RuntimeLock guard;
        if (emulatorClients.empty()) return;
        recipients = emulatorClients;
        fullRecipients = clientsNeedingFullFrame;
        for (uint32_t id : recipients) clientsNeedingFullFrame.erase(id);
        const LedController &led = animationController.getLedController();
        memcpy(frame.data(), &led.ledColors[0][0][0], bufferSize);
    }
    const uint8_t *currentData = frame.data();

    // Initialize lastLedData if empty
    if (lastLedData.empty())
    {
        lastLedData.resize(bufferSize, 0);
    }
    // Calculate Diff
    // Format: [Type(1), Count(2), [Index(2), R, G, B]...]
    std::vector<uint8_t> diffPayload;

    // Reuse diffPayload buffer
    diffPayload.clear();
    diffPayload.push_back(1); // Type 1 = Diff
    diffPayload.push_back(0); // Count High placeholder
    diffPayload.push_back(0); // Count Low placeholder

    uint16_t changeCount = 0;
    // Iterate pixels
    for (size_t i = 0; i < bufferSize / 3; i++)
    {
        size_t idx = i * 3;
        if (currentData[idx] != lastLedData[idx] ||
            currentData[idx + 1] != lastLedData[idx + 1] ||
            currentData[idx + 2] != lastLedData[idx + 2])
        {
            changeCount++;
            // Index (2 bytes)
            diffPayload.push_back((i >> 8) & 0xFF);
            diffPayload.push_back(i & 0xFF);
            // RGB
            diffPayload.push_back(currentData[idx]);
            diffPayload.push_back(currentData[idx + 1]);
            diffPayload.push_back(currentData[idx + 2]);
        }
    }

    // Update count in payload
    diffPayload[1] = (changeCount >> 8) & 0xFF;
    diffPayload[2] = changeCount & 0xFF;

    // Determine if we should send Full or Diff
    // Full payload size: 1 (Type) + bufferSize
    // Diff payload size: diffPayload.size()
    bool preferFull = (diffPayload.size() > (bufferSize + 1));

    // Prepare Full Payload if needed
    // We construct it on demand to avoid memory usage if not needed,
    // or we could use a static buffer.
    // Let's just create a vector for it if we need it.
    std::vector<uint8_t> fullPayload;
    if (preferFull || !fullRecipients.empty())
    {
        fullPayload.clear();
        fullPayload.reserve(bufferSize + 1);
        fullPayload.push_back(0); // Type 0 = Full
        fullPayload.insert(fullPayload.end(), currentData, currentData + bufferSize);
    }

    for (uint32_t id : recipients)
    {
        bool needsFull = fullRecipients.count(id) > 0;

        if (needsFull || preferFull)
        {
            ws.binary(id, fullPayload.data(), fullPayload.size());
        }
        else
        {
            ws.binary(id, diffPayload.data(), diffPayload.size());
        }
    }

    // Update lastLedData
    memcpy(lastLedData.data(), currentData, bufferSize);
}

String ChromanceWebServer::getStatusJson()
{
    struct AnimationStatus {
        int id;
        const char *name;
        bool enabled;
        bool hasConfig;
    };
    // Registry membership is immutable after init(), before the web server
    // starts. Reserve outside the render lock so the snapshot cannot allocate.
    const int count = animationController.getAnimationCount();
    std::vector<AnimationStatus> animations;
    animations.reserve(count);
    byte currentAnimation;
    bool autoSwitching;
    bool sleepEnabled;
    bool autoResumePending;
    uint32_t autoResumeRemainingSeconds;
    int autoResumeMinutes;
    {
        RuntimeLock guard;
        currentAnimation = animationController.getCurrentAnimation();
        autoSwitching = animationController.isAutoSwitching();
        sleepEnabled = configuration.isSleepEnabled();
        autoResumeMinutes = configuration.getAutoResumeMinutes();
        autoResumePending = animationController.isAutoResumePending();
        autoResumeRemainingSeconds = animationController.getAutoResumeRemainingSeconds();
        for (int i = 0; i < count; ++i)
        {
            Animation *anim = animationController.getAnimation(i);
            if (anim)
                animations.push_back({i, anim->getName(), anim->isEnabled(), anim->hasConfig()});
        }
    }

    // JSON allocations, ESP diagnostics and serialization must not delay the
    // renderer. Names are static literals owned by the long-lived animations.
    JsonDocument doc;
    doc["type"] = "status";
    doc["uptimeMs"] = millis();
    doc["firmwareRevision"] = "sleep-auto-resume-1";
#ifdef ESP32
    doc["freeHeap"] = ESP.getFreeHeap();
    doc["resetReason"] = static_cast<int>(esp_reset_reason());
    doc["sleepWakeupCause"] = static_cast<int>(esp_sleep_get_wakeup_cause());
    doc["arduinoVersion"] = String(ESP_ARDUINO_VERSION_MAJOR) + "." +
        String(ESP_ARDUINO_VERSION_MINOR) + "." + String(ESP_ARDUINO_VERSION_PATCH);
    doc["idfVersion"] = ESP.getSdkVersion();
#endif
    doc["currentAnimation"] = currentAnimation;
    doc["autoSwitching"] = autoSwitching;
    doc["sleepEnabled"] = sleepEnabled;
    doc["autoResumeMinutes"] = autoResumeMinutes;
    doc["autoResumePending"] = autoResumePending;
    doc["autoResumeRemainingSeconds"] = autoResumeRemainingSeconds;

    JsonArray anims = doc["animations"].to<JsonArray>();
    for (const AnimationStatus &anim : animations)
    {
        JsonObject animObj = anims.add<JsonObject>();
        animObj["id"] = anim.id;
        animObj["name"] = anim.name;
        animObj["enabled"] = anim.enabled;
        animObj["hasConfig"] = anim.hasConfig;
    }

    String jsonString;
    serializeJson(doc, jsonString);
    return jsonString;
}

String ChromanceWebServer::getEmulatorConfigJson()
{
    JsonDocument doc;
    doc["type"] = "config";
    doc["ledsPerSegment"] = Constants::LEDS_PER_SEGMENT;

    JsonArray nodes = doc["nodePositions"].to<JsonArray>();
    for (int i = 0; i < Constants::NUMBER_OF_NODES; i++)
    {
        JsonObject n = nodes.add<JsonObject>();
        n["x"] = Topology::nodePositions[i].x;
        n["y"] = Topology::nodePositions[i].y;
    }

    JsonArray segs = doc["segmentConnections"].to<JsonArray>();
    for (int i = 0; i < Constants::NUMBER_OF_SEGMENTS; i++)
    {
        JsonArray s = segs.add<JsonArray>();
        s.add(Topology::segmentConnections[i][0]);
        s.add(Topology::segmentConnections[i][1]);
    }

    String jsonString;
    serializeJson(doc, jsonString);
    return jsonString;
}
