---
name: chromium-dino-runner
description: Programmatic interface to the Chromium offline T-Rex (dino) game's `Runner` singleton from automation code (Selenium/Playwright/CDP). Covers the modern singleton API, state fields, score formula, kickoff/restart sequencing, and the legacy `Runner.instance_` pitfall.
---

# chromium-dino-runner

How to drive the Chromium offline dino game from automation code (Selenium / CDP).

## Source of truth

- [`components/neterror/resources/dino_game/offline.ts`](https://source.chromium.org/chromium/chromium/src/+/main:components/neterror/resources/dino_game/offline.ts)
- [`distance_meter.ts`](https://source.chromium.org/chromium/chromium/src/+/main:components/neterror/resources/dino_game/distance_meter.ts)
- [`trex.ts`](https://source.chromium.org/chromium/chromium/src/+/main:components/neterror/resources/dino_game/trex.ts)
- [`obstacle.ts`](https://source.chromium.org/chromium/chromium/src/+/main:components/neterror/resources/dino_game/obstacle.ts)

Verified against Chrome 148.0.7778.56 (April 2026). Re-check on major version bumps.

## How to load the page

The dino game ships as `chrome://dino` and as the offline interstitial of `chrome://network-error/-106` (`ERR_INTERNET_DISCONNECTED`). The cleanest automation path:

1. Launch Chrome via Selenium/CDP.
2. Send `Network.emulateNetworkConditions {"offline": true, ...}` via CDP.
3. `driver.get("http://chrome-dino-offline.invalid/")` — Selenium will raise `WebDriverException: net::ERR_INTERNET_DISCONNECTED`, **swallow it**. The offline interstitial *is* the page you want.
4. `chrome://dino` direct nav also works on most builds but some versions throw — use the unreachable-URL path as the canonical fallback.

## Singleton API — modern (Chrome ≥ ~120)

The runner is module-private. **`Runner.instance_` no longer exists.** Use these two static methods:

```js
Runner.getInstance()        // returns the live Runner; asserts non-null (page has bootstrapped)
Runner.initializeInstance(outerContainerId, config?)  // called ONCE by the page; calling again triggers assert(runnerInstance === null)
```

The page initializes the instance itself when offline.js loads. **Do not call `initializeInstance` from your automation** — it will throw `Assertion failed`. Just `Runner.getInstance()`.

Common probe to detect API generation:
```js
typeof Runner.getInstance === 'function'   // modern
typeof Runner.instance_ !== 'undefined'    // legacy (pre-TS rewrite)
```

## State fields

All `private` in TypeScript but readable at runtime as plain JS properties on the `Runner` object:

| Field | Type | Notes |
|---|---|---|
| `playing` | bool | `true` after first jump key sets `setPlayStatus(true)` |
| `crashed` | bool | `true` after collision; stays true until `restart()` |
| `activated` | bool | `true` after `playIntro()` |
| `paused` | bool | true if tab loses focus (`onVisibilityChange`) |
| `currentSpeed` | number | starts at `config.speed = 6`; ramps to `maxSpeed = 13` |
| `distanceRan` | number | pixel distance accumulated; **not** the displayed score |
| `time` | number | `getTimeStamp()` of last update |
| `playCount` | int | bumped on `startGame()`/`restart()` |
| `tRex` | Trex \| null | `null` until `init()` finishes (after image load) |
| `horizon` | Horizon \| null | same |
| `distanceMeter` | DistanceMeter \| null | same |

`tRex` exposes `xPos`, `yPos` (≈93 = ground), `jumping`, `ducking`, `speedDrop`.

`horizon.obstacles` is an array; each entry has:
- `xPos`, `yPos`, `width`
- `typeConfig.{ type, width, height }` — `type` ∈ `{'CACTUS_SMALL', 'CACTUS_LARGE', 'PTERODACTYL', 'collectable', ...}`
- `size` — multiplicity (1..3 cacti glued together)

## Score formula (the only correct one)

From [`distance_meter.ts`](https://source.chromium.org/chromium/chromium/src/+/main:components/neterror/resources/dino_game/distance_meter.ts) `getActualDistance(distance)`:

```js
score = distanceRan ? Math.round(Math.ceil(distanceRan) * 0.025) : 0
```

`COEFFICIENT = 0.025`. Note: it's `Math.round(Math.ceil(...))`, **not** `Math.floor(...)`. `Math.floor(distanceRan * 0.025)` is approximately right but drifts by ±1 against the on-screen number.

Equivalent live read:
```js
Runner.getInstance().distanceMeter.getActualDistance(Math.ceil(Runner.getInstance().distanceRan))
```
…but `distanceMeter` is null pre-init, so guard for that.

## Kickoff sequence

1. Page loads → `runnerInstance` constructor runs → `loadImages()` queued.
2. After image `load` event → `init()` runs → `tRex`, `horizon`, `distanceMeter` populated; `activated=false`, `playing=false`.
3. Automation sends Space (`keyCode 32`) keydown via CDP.
4. `onKeyDown` → `setPlayStatus(true)` + `update()` + `tRex.startJump()`.
5. First jump triggers `playIntro()` → CSS animation → on `webkitAnimationEnd` → `startGame()` (`activated=true`, `runningTime=0`).

Steps 2 → 3 may race. Wait for `Runner.getInstance().tRex !== null` before sending the kickoff Space.

## Action dispatch via CDP

Use `Input.dispatchKeyEvent`. The runner listens to plain `keydown`/`keyup` on `document`:

```python
driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
    "type": "keyDown",   # or "keyUp"
    "key": " ",          # " " for space, "ArrowUp", "ArrowDown"
    "code": "Space",     # "Space", "ArrowUp", "ArrowDown"
    "windowsVirtualKeyCode": 32,  # 32 space, 38 up, 40 down, 13 enter
})
```

`runnerKeycodes` (from `offline.ts`):
- `jump: [38, 32]` — ArrowUp or Space
- `duck: [40]` — ArrowDown
- `restart: [13]` — Enter

For DUCK to take effect, send keydown and **hold** until you want to stand up. Releasing ArrowDown calls `tRex.setDuck(false)`.

## Restart after crash

From `onKeyUp`: when `crashed === true`, a jump key (Space/ArrowUp) only restarts if `getTimeStamp() - this.time >= config.gameoverClearTime` (1200 ms by default). Wait at least 1.2 s after the crash before sending the restart Space, or use Enter (key 13) which has no delay gate.

## Game-over detection

`Runner.getInstance().crashed === true` flips synchronously inside `update()` when `checkForCollision` returns truthy. Poll at your control loop's tempo; the value is stable once set.

## Visibility/focus pitfall

`onVisibilityChange` is bound to `document.visibilitychange`, `window.blur`, and `window.focus`. If your automation runs Chrome headfully and the user clicks another window, the game pauses (`stop()` called, `paused=true`). For deterministic eval runs, either run headless or call `Runner.getInstance().play()` to resume after focus loss (it returns `void` and only resumes if `!crashed`).

## Common mistakes

- **Calling `Runner.initializeInstance(...)` from automation** — page already did it; you'll hit `Assertion failed`.
- **Reading `Runner.instance_`** — undefined on modern Chrome; returns the singleton only on legacy builds (≤ ~115).
- **Computing score as `Math.floor(distanceRan * 0.025)`** — off-by-one vs displayed score. Use `Math.round(Math.ceil(...) * 0.025)`.
- **Sending restart Space immediately after crash** — silently ignored for first 1.2 s. Either wait or use Enter.
- **Treating `tRex.yPos === 93` as a magic constant** — true for default sprite at default canvas height (150) but coupled to sprite definition; read it from `Runner.getInstance().tRex.groundYPos` if you need exact ground level.
- **Expecting `chrome://dino` to navigate cleanly on every Chrome build** — Chrome-for-Testing builds sometimes throw on the `chrome://` scheme. Fall back to an unreachable URL.
