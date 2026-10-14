#include "AnimationController.h"
#include "AnimationRegistry.h"
#include "animations/Animation.h"
#include "RuntimeLock.h"

AnimationController::AnimationController(LedController &controller, Configuration &config)
    : ledController(controller), configuration(config)
{
  for (int i = 0; i < Constants::NUMBER_OF_RIPPLES; i++)
  {
    ripples[i] = Ripple(i);
  }
}

AnimationController::~AnimationController()
{
  for (auto anim : animations)
  {
    if (anim != nullptr)
    {
      delete anim;
    }
  }
  animations.clear();
}

void AnimationController::recalculateAutoPulseTypes()
{
  RuntimeLock guard;
  numberOfAutoPulseTypes = 0;
  for (auto anim : animations)
  {
    if (anim != nullptr && anim->isEnabled())
    {
      numberOfAutoPulseTypes++;
    }
  }
}

void AnimationController::init()
{
  RuntimeLock guard;
  if (animations.empty())
  {
    auto entries = AnimationRegistry::getInstance().getSortedEntries();
    for (const auto &entry : entries)
    {
        animations.push_back(entry.factory(*this));
    }
  }

  recalculateAutoPulseTypes();

  baseColor = random(0xFFFF);
  lastRandomPulse = millis();
}

void AnimationController::update()
{
  RuntimeLock guard;
  if (autoResumePending &&
      uint32_t(uint32_t(millis()) - manualPauseStartedAt) >=
          uint32_t(configuration.getAutoResumeMinutes()) * 60000U)
  {
    // Resume through the normal scheduling path below; never run an effect
    // twice or advance a ripple twice when the manual window expires.
    setAutoSwitching(true);
  }
  // Fade all dots to create trails
  float decay = 0.97f;
  ledController.fade(decay);

  // Advance ripples
  for (int i = 0; i < Constants::NUMBER_OF_RIPPLES; i++)
  {
    ripples[i].advance(ledController);
  }

  // Update current animation
  if (currentAutoPulseType < animations.size() && animations[currentAutoPulseType])
  {
    animations[currentAutoPulseType]->update();
  }

  // Check for new animation trigger
  if (numberOfAutoPulseTypes > 0 && millis() - lastRandomPulse >= Constants::randomPulseTime)
  {
    bool readyToSwitch = true;

    if (currentAutoPulseType < animations.size() && animations[currentAutoPulseType])
    {
      if (!animations[currentAutoPulseType]->canBePreempted() && !animations[currentAutoPulseType]->isFinished())
      {
        readyToSwitch = false;
      }
    }

    if (readyToSwitch)
    {
      if (autoSwitching)
      {
        const byte previous = currentAutoPulseType;
        const byte next = getNextAnimation();
        // Continuous effects keep their phase throughout their 30-second slot.
        // Finite effects can still launch a new pulse every two seconds.
        if (previous != next ||
            (previous < animations.size() && animations[previous]->isFinished()))
        {
          baseColor = random(0xFFFF);
          startAnimation(next);
        }

        lastRandomPulse = millis();
      }
      else
      {
        // Manual mode
        if (currentAutoPulseType < animations.size() && animations[currentAutoPulseType] && animations[currentAutoPulseType]->isFinished())
        {
          rollNewBaseColor();
          animations[currentAutoPulseType]->run();
          lastRandomPulse = millis();
        }
      }
    }
  }

  // Present this frame, after the animation has rendered it.
  ledController.show();
}

void AnimationController::rollNewBaseColor()
{
  unsigned int prev = baseColor;
  int attempts = 0;
  do {
    baseColor = random(0xFFFF);
  } while (baseColor == prev && attempts++ < 16);
  if (baseColor == prev)
    baseColor = (prev + 0x8000) & 0xFFFF;
}

byte AnimationController::getNextAnimation()
{
  if (currentAutoPulseType == 255 || (numberOfAutoPulseTypes > 1 && millis() - lastAutoPulseChange >= Constants::RIPPLE_TIMEOUT))
  {
    byte possiblePulse = 255;
    int attempts = 0;
    while (attempts < 100)
    {
      if (animations.empty()) break;
      
      possiblePulse = random(animations.size());

      if (possiblePulse == currentAutoPulseType)
      {
        attempts++;
        continue;
      }

      if (animations[possiblePulse] != nullptr && animations[possiblePulse]->isEnabled())
      {
        return possiblePulse;
      }
      attempts++;
    }
  }
  return currentAutoPulseType;
}

void AnimationController::startAnimation(byte animation)
{
  RuntimeLock guard;
  if (animation >= animations.size() || !animations[animation]) return;
  if (animation != currentAutoPulseType)
  {
    if (currentAutoPulseType < animations.size() && animations[currentAutoPulseType])
      animations[currentAutoPulseType]->stop();
    // A different effect owns a fresh canvas and ripple pool. Re-running the
    // same finite effect intentionally preserves overlapping pulses/trails.
    for (auto &ripple : ripples) ripple.state = STATE_DEAD;
    Ripple::runnerNode = -1;
    ledController.clear();
    lastAutoPulseChange = millis();
  }
  currentAutoPulseType = animation;
  if (animation < animations.size() && animations[animation])
  {
    animations[animation]->run();
  }
  notifyStateChange();
}

void AnimationController::changeAnimation(byte animation)
{
  RuntimeLock guard;
  if (animation >= animations.size()) return;
  if (!autoSwitching) restartAutoResumeTimer();
  rollNewBaseColor();
  startAnimation(animation);
}

uint32_t AnimationController::getRandomColor()
{
  return ledController.ColorHSV(baseColor, 255, 255);
}

float AnimationController::getSpeed()
{
  return random(500, 800) / 1000.0f;
}

void AnimationController::startRipple(int node, int direction, uint32_t color, float speed, unsigned long lifespan, RippleBehavior behavior)
{
  for (int j = 0; j < Constants::NUMBER_OF_RIPPLES; j++)
  {
    if (ripples[j].state == STATE_DEAD)
    {
      ripples[j].start(
          node,
          direction,
          color,
          speed,
          lifespan,
          behavior);
      break;
    }
  }
}

byte AnimationController::getLastNode()
{
  return lastAutoPulseNode;
}

void AnimationController::setLastNode(byte node)
{
  lastAutoPulseNode = node;
}

LedController &AnimationController::getLedController()
{
  return ledController;
}

unsigned int AnimationController::getBaseColor()
{
  return baseColor;
}

int AnimationController::getActiveRippleCount() const
{
  int count = 0;
  for (int i = 0; i < Constants::NUMBER_OF_RIPPLES; i++)
  {
    if (ripples[i].state != STATE_DEAD)
    {
      count++;
    }
  }
  return count;
}

void AnimationController::setAutoSwitching(bool enabled)
{
  RuntimeLock guard;
  autoSwitching = enabled;
  if (enabled) autoResumePending = false;
  else restartAutoResumeTimer();
  notifyStateChange();
}

void AnimationController::restartAutoResumeTimer()
{
  manualPauseStartedAt = uint32_t(millis());
  autoResumePending = configuration.getAutoResumeMinutes() > 0;
}

void AnimationController::onAutoResumeSettingChanged()
{
  RuntimeLock guard;
  if (!autoSwitching) restartAutoResumeTimer();
  notifyStateChange();
}

uint32_t AnimationController::getAutoResumeRemainingSeconds() const
{
  if (!autoResumePending) return 0;
  const uint32_t duration = uint32_t(configuration.getAutoResumeMinutes()) * 60000U;
  const uint32_t elapsed = uint32_t(uint32_t(millis()) - manualPauseStartedAt);
  return elapsed >= duration ? 0 : (duration - elapsed + 999U) / 1000U;
}

Ripple &AnimationController::getRipple(int index)
{
  if (index < 0 || index >= Constants::NUMBER_OF_RIPPLES)
  {
    return ripples[0];
  }
  return ripples[index];
}

Animation *AnimationController::getAnimation(int index)
{
  if (index < 0 || index >= animations.size())
  {
    return nullptr;
  }
  return animations[index];
}

void AnimationController::notifyStateChange()
{
  if (stateChangeCallback)
  {
    stateChangeCallback(currentAutoPulseType, autoSwitching);
  }
}
