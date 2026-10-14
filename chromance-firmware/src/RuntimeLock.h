#ifndef RUNTIME_LOCK_H
#define RUNTIME_LOCK_H

#if defined(ESP32) && !defined(NATIVE_TEST)
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#else
#include <mutex>
#endif

// Shared across translation units. Controller::init creates the mutex before
// asynchronous tasks start; recursion permits animation callbacks into it.
class RuntimeLock
{
public:
    RuntimeLock()
    {
#if defined(ESP32) && !defined(NATIVE_TEST)
        const BaseType_t acquired = xSemaphoreTakeRecursive(mutex(), portMAX_DELAY);
        configASSERT(acquired == pdTRUE);
#else
        mutex().lock();
#endif
    }

    ~RuntimeLock()
    {
#if defined(ESP32) && !defined(NATIVE_TEST)
        xSemaphoreGiveRecursive(mutex());
#else
        mutex().unlock();
#endif
    }

    RuntimeLock(const RuntimeLock &) = delete;
    RuntimeLock &operator=(const RuntimeLock &) = delete;

private:
#if defined(ESP32) && !defined(NATIVE_TEST)
    static SemaphoreHandle_t mutex()
    {
        static SemaphoreHandle_t handle = xSemaphoreCreateRecursiveMutex();
        configASSERT(handle != nullptr);
        return handle;
    }
#else
    static std::recursive_mutex &mutex()
    {
        static std::recursive_mutex handle;
        return handle;
    }
#endif
};

#endif
