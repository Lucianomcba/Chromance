#ifndef SLEEP_CONTROL_H
#define SLEEP_CONTROL_H

// Queues one fixed 30-second validation sleep, with response grace and a dark
// observation pause. Returns false when OTA or another sleep is in progress.
bool requestDeepSleepValidation();

#endif
