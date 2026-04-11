"""Tests for DinoEnv v2 features — written from spec, before implementation."""

import numpy as np
import pytest
from gymnasium import spaces

from src.env import (
    CANVAS_WIDTH,
    DROP_VELOCITY,
    FPS,
    GRAVITY,
    INITIAL_JUMP_VELOCITY,
    INITIAL_SPEED,
    MAX_JUMP_HEIGHT,
    MAX_SPEED,
    MIN_JUMP_HEIGHT,
    DinoEnv,
)

# ---------------------------------------------------------------------------
# Actions (from spec)
# ---------------------------------------------------------------------------
ACTION_NOOP = 0
ACTION_JUMP = 1
ACTION_DUCK = 2


# ===================================================================
# Helpers
# ===================================================================

def make_env(**kwargs):
    """Create a DinoEnv and reset it, returning (env, obs, info)."""
    env = DinoEnv(**kwargs)
    obs, info = env.reset(seed=42)
    return env, obs, info


def step_n(env, action, n):
    """Take *n* steps with the same action, returning the last transition."""
    obs = terminated = truncated = None
    total_reward = 0.0
    for _ in range(n):
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break
    return obs, total_reward, terminated, truncated, info


# ===================================================================
# 1. Action Delay Tests
# ===================================================================

class TestActionDelay:
    """Spec §1 — action_delay parameter."""

    def test_default_is_zero(self):
        """action_delay defaults to 0 (backward compat)."""
        env = DinoEnv()
        assert env.action_delay == 0
        env.close()

    def test_delay_zero_jump_immediate(self):
        """With action_delay=0, jump action takes effect on the same step."""
        env, _, _ = make_env(action_delay=0)
        obs, _, _, _, _ = env.step(ACTION_JUMP)
        # T-Rex should already be airborne (y > 0) after one step.
        # Observation layout: the T-Rex y position is exposed in the obs vector.
        # We verify indirectly: the dino's y should have increased.
        assert env.trex_y > 0, "With delay=0, jump should take effect immediately"
        env.close()

    def test_delay_one_jump_one_step_late(self):
        """With action_delay=1, jump issued at step 0 applies at step 1."""
        env, _, _ = make_env(action_delay=1)

        # Step 0: send JUMP — but the executed action should be the noop
        # that pre-filled the buffer, so dino stays grounded.
        env.step(ACTION_JUMP)
        y_after_step0 = env.trex_y
        assert y_after_step0 == 0, "Delay=1: jump should NOT apply at step 0"

        # Step 1: send NOOP — the dequeued action should be the JUMP from step 0.
        env.step(ACTION_NOOP)
        y_after_step1 = env.trex_y
        assert y_after_step1 > 0, "Delay=1: jump from step 0 should apply at step 1"
        env.close()

    def test_delay_two_jump_two_steps_late(self):
        """With action_delay=2, jump issued at step 0 applies at step 2."""
        env, _, _ = make_env(action_delay=2)

        env.step(ACTION_JUMP)  # step 0: enqueue JUMP
        assert env.trex_y == 0, "Delay=2: jump should NOT apply at step 0"

        env.step(ACTION_NOOP)  # step 1: still noop from pre-filled buffer
        assert env.trex_y == 0, "Delay=2: jump should NOT apply at step 1"

        env.step(ACTION_NOOP)  # step 2: JUMP dequeued
        assert env.trex_y > 0, "Delay=2: jump from step 0 should apply at step 2"
        env.close()

    def test_buffer_clears_on_reset(self):
        """After reset(), the action buffer is cleared and re-filled with noops."""
        env, _, _ = make_env(action_delay=2)

        # Enqueue a couple of jumps.
        env.step(ACTION_JUMP)
        env.step(ACTION_JUMP)

        # Reset — buffer should be all noops again.
        env.reset(seed=42)

        # Two noop steps should leave the dino grounded (buffered jumps gone).
        env.step(ACTION_NOOP)
        env.step(ACTION_NOOP)
        assert env.trex_y == 0, "After reset, buffered actions should be cleared"
        env.close()

    def test_fifo_ordering(self):
        """Actions are dequeued in FIFO order."""
        env, _, _ = make_env(action_delay=2)

        # Pre-fill: [NOOP, NOOP]
        # Step 0: enqueue JUMP  → buffer [NOOP, JUMP], execute NOOP
        # Step 1: enqueue DUCK  → buffer [JUMP, DUCK], execute NOOP
        # Step 2: enqueue NOOP  → buffer [DUCK, NOOP], execute JUMP  ← airborne
        env.step(ACTION_JUMP)
        env.step(ACTION_DUCK)

        # Step 2 should execute the JUMP from step 0.
        env.step(ACTION_NOOP)
        assert env.trex_y > 0, "FIFO: JUMP queued first should execute first"
        env.close()

    def test_negative_delay_rejected(self):
        """action_delay < 0 should raise ValueError."""
        with pytest.raises((ValueError, AssertionError)):
            DinoEnv(action_delay=-1)


# ===================================================================
# 2. Frame Skip Tests
# ===================================================================

class TestFrameSkip:
    """Spec §2 — frame_skip parameter."""

    def test_default_is_one(self):
        """frame_skip defaults to 1 (backward compat)."""
        env = DinoEnv()
        assert env.frame_skip == 1
        env.close()

    def test_frame_skip_one_same_as_v1(self):
        """With frame_skip=1, one step = one internal frame."""
        env1, obs1, _ = make_env(frame_skip=1)
        env2, obs2, _ = make_env()  # default

        for _ in range(10):
            o1, r1, t1, tr1, _ = env1.step(ACTION_NOOP)
            o2, r2, t2, tr2, _ = env2.step(ACTION_NOOP)
            np.testing.assert_array_equal(o1, o2)
            assert r1 == r2

        env1.close()
        env2.close()

    def test_frame_skip_advances_multiple_frames(self):
        """frame_skip=K causes a single step to advance K frames."""
        env_k1, _, _ = make_env(frame_skip=1)
        env_k3, _, _ = make_env(frame_skip=3)

        # Advance env_k1 by 3 individual steps.
        for _ in range(3):
            obs_k1, _, _, _, _ = env_k1.step(ACTION_NOOP)

        # Advance env_k3 by 1 step (= 3 internal frames).
        obs_k3, _, _, _, _ = env_k3.step(ACTION_NOOP)

        np.testing.assert_array_almost_equal(
            obs_k1, obs_k3,
            err_msg="frame_skip=3 should equal 3 individual steps",
        )
        env_k1.close()
        env_k3.close()

    def test_reward_accumulated(self):
        """Reward is summed across all K internal frames."""
        env_k1, _, _ = make_env(frame_skip=1)
        env_k4, _, _ = make_env(frame_skip=4)

        cumulative_r = 0.0
        for _ in range(4):
            _, r, _, _, _ = env_k1.step(ACTION_NOOP)
            cumulative_r += r

        _, r_k4, _, _, _ = env_k4.step(ACTION_NOOP)

        assert r_k4 == pytest.approx(cumulative_r), (
            "Reward should be summed across all frame_skip frames"
        )
        env_k1.close()
        env_k4.close()

    def test_early_termination(self):
        """If game ends during frame skip, step returns immediately."""
        env, _, _ = make_env(frame_skip=100)
        # Run until the episode terminates.
        terminated = False
        for _ in range(10_000):
            _, _, terminated, truncated, _ = env.step(ACTION_NOOP)
            if terminated or truncated:
                break
        # The episode must eventually end — the skip should not suppress termination.
        assert terminated or truncated, "Early termination should be detected during frame skip"
        env.close()

    def test_observation_from_last_frame(self):
        """The returned observation should be from the last internal frame."""
        env_k1, _, _ = make_env(frame_skip=1)
        env_k5, _, _ = make_env(frame_skip=5)

        # Step env_k1 five times.
        for _ in range(5):
            obs_last, _, _, _, _ = env_k1.step(ACTION_NOOP)

        obs_k5, _, _, _, _ = env_k5.step(ACTION_NOOP)

        np.testing.assert_array_almost_equal(
            obs_last, obs_k5,
            err_msg="Observation should match the last internal frame",
        )
        env_k1.close()
        env_k5.close()

    def test_frame_skip_below_one_rejected(self):
        """frame_skip < 1 should raise ValueError."""
        with pytest.raises((ValueError, AssertionError)):
            DinoEnv(frame_skip=0)


# ===================================================================
# 3. Speed-Dependent Jump Velocity Tests
# ===================================================================

class TestSpeedDependentJump:
    """Spec §3 — jump velocity = INITIAL_JUMP_VELOCITY + speed / 10."""

    def _get_trex_y_after_jump(self, env):
        """Issue a jump and return the trex_y one frame after."""
        env.step(ACTION_JUMP)
        return env.trex_y

    def test_jump_velocity_at_initial_speed(self):
        """At speed=INITIAL_SPEED (6), velocity should be 10 + 0.6 = 10.6."""
        env, _, _ = make_env()
        y = self._get_trex_y_after_jump(env)
        expected_vel = INITIAL_JUMP_VELOCITY + INITIAL_SPEED / 10  # 10.6
        # After one frame: gravity applied same frame → y = vel - gravity
        expected_y = expected_vel - GRAVITY  # 10.0
        assert y == pytest.approx(expected_y), (
            f"First-frame y should be {expected_y}, got {y}"
        )
        env.close()

    def test_jump_velocity_at_max_speed(self):
        """At speed=MAX_SPEED (13), velocity should be 10 + 1.3 = 11.3."""
        env, _, _ = make_env(clear_time_ms=999_999)  # no obstacles
        # Set speed directly — we're testing physics, not obstacle avoidance.
        env.speed = MAX_SPEED
        y = self._get_trex_y_after_jump(env)
        expected_vel = INITIAL_JUMP_VELOCITY + MAX_SPEED / 10  # 11.3
        expected_y = expected_vel - GRAVITY  # 10.7
        assert y == pytest.approx(expected_y), (
            f"First-frame y at max speed should be {expected_y}, got {y}"
        )
        env.close()

    def test_higher_speed_means_higher_peak(self):
        """Peak height at speed=MAX_SPEED should exceed peak height at speed=INITIAL_SPEED."""
        # --- Peak at initial speed ---
        env_slow, _, _ = make_env(clear_time_ms=999_999)
        env_slow.step(ACTION_JUMP)
        peak_slow = env_slow.trex_y
        for _ in range(200):
            env_slow.step(ACTION_NOOP)
            if env_slow.trex_y > peak_slow:
                peak_slow = env_slow.trex_y
            if env_slow.trex_y == 0:
                break

        # --- Peak at max speed ---
        env_fast, _, _ = make_env(clear_time_ms=999_999)
        env_fast.speed = MAX_SPEED
        env_fast.step(ACTION_JUMP)
        peak_fast = env_fast.trex_y
        for _ in range(200):
            env_fast.step(ACTION_NOOP)
            if env_fast.trex_y > peak_fast:
                peak_fast = env_fast.trex_y
            if env_fast.trex_y == 0:
                break

        assert peak_fast > peak_slow, (
            f"Peak at max speed ({peak_fast}) should exceed initial speed ({peak_slow})"
        )
        env_slow.close()
        env_fast.close()

    def test_velocity_increases_with_speed(self):
        """Jump velocity should be strictly increasing with speed."""
        env, _, _ = make_env(clear_time_ms=999_999)  # no obstacles
        velocities = []
        speeds = []

        for target_speed in [6.0, 8.0, 10.0, 12.0, 13.0]:
            env.speed = target_speed
            speeds.append(env.speed)
            env.step(ACTION_JUMP)
            velocities.append(env.trex_y)
            # Wait to land.
            for _ in range(200):
                env.step(ACTION_NOOP)
                if env.trex_y == 0:
                    break

        # Velocities should be strictly monotonically increasing.
        for i in range(1, len(velocities)):
            assert velocities[i] > velocities[i - 1], (
                f"Jump velocity at speed {speeds[i]} ({velocities[i]}) "
                f"should exceed speed {speeds[i-1]} ({velocities[i-1]})"
            )
        env.close()


# ===================================================================
# 4. Configurable clearTime Tests
# ===================================================================

class TestClearTime:
    """Spec §4 — clear_time_ms parameter."""

    def test_default_clear_time(self):
        """Default clear_time_ms is 500."""
        env = DinoEnv()
        assert env.clear_time_ms == 500
        env.close()

    def test_no_obstacles_before_clear_time(self):
        """No obstacles should spawn before clear_time_ms / 1000 * 60 frames."""
        clear_ms = 3000
        safe_frames = int(clear_ms / 1000 * FPS)  # 180 frames
        env, _, _ = make_env(clear_time_ms=clear_ms)

        for frame in range(safe_frames):
            obs, _, terminated, truncated, _ = env.step(ACTION_NOOP)
            if terminated or truncated:
                pytest.fail(
                    f"Episode terminated at frame {frame} which is before "
                    f"clear_time ({safe_frames} frames). "
                    "No obstacles should exist in the clear window."
                )
            # Obstacle count or first obstacle distance in obs should indicate none.
            # With no obstacles, the agent should never collide.
            # (The strongest spec guarantee: no obstacles ⇒ no collision.)
        env.close()

    def test_obstacles_appear_after_clear_time(self):
        """Obstacles should eventually spawn after the clear time has passed."""
        clear_ms = 500
        safe_frames = int(clear_ms / 1000 * FPS)  # 30 frames
        env, _, _ = make_env(clear_time_ms=clear_ms)

        # Fast-forward past clear time.
        step_n(env, ACTION_NOOP, safe_frames)

        # Run for a generous window — obstacles should appear.
        obstacle_seen = False
        for _ in range(2000):
            obs, _, terminated, truncated, _ = env.step(ACTION_NOOP)
            if terminated or truncated:
                # Collision ⇒ obstacle existed.
                obstacle_seen = True
                break
        assert obstacle_seen, (
            "Obstacles should eventually spawn after the clear time window"
        )
        env.close()

    def test_large_clear_time(self):
        """With a very large clear_time_ms, many noop steps should be safe."""
        env, _, _ = make_env(clear_time_ms=10_000)
        safe_frames = int(10_000 / 1000 * FPS)  # 600 frames

        for frame in range(safe_frames):
            _, _, terminated, truncated, _ = env.step(ACTION_NOOP)
            if terminated or truncated:
                pytest.fail(
                    f"Episode ended at frame {frame}, but clear_time_ms=10000 "
                    f"should guarantee {safe_frames} obstacle-free frames."
                )
        env.close()


# ===================================================================
# 5. Backward Compatibility / Combined Tests
# ===================================================================

class TestBackwardCompatibility:
    """Spec §5 — defaults should match v1."""

    def test_default_observation_space(self):
        env = DinoEnv()
        assert env.observation_space.shape == (20,)
        np.testing.assert_array_equal(env.observation_space.low, -np.ones(20))
        np.testing.assert_array_equal(env.observation_space.high, np.ones(20))
        env.close()

    def test_default_action_space(self):
        env = DinoEnv()
        assert isinstance(env.action_space, spaces.Discrete)
        assert env.action_space.n == 3
        env.close()

    def test_defaults_match_v1(self):
        """DinoEnv() with no args should have v1 defaults."""
        env = DinoEnv()
        assert env.action_delay == 0
        assert env.frame_skip == 1
        assert env.clear_time_ms == 500
        env.close()

    def test_reset_returns_valid_obs(self):
        env = DinoEnv()
        obs, info = env.reset(seed=42)
        assert obs.shape == (20,)
        assert env.observation_space.contains(obs)
        env.close()

    def test_step_returns_valid_obs(self):
        env, _, _ = make_env()
        obs, reward, terminated, truncated, info = env.step(ACTION_NOOP)
        assert obs.shape == (20,)
        assert env.observation_space.contains(obs)
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        env.close()


class TestCombinedFeatures:
    """Multiple v2 features working together."""

    def test_delay_and_frameskip_together(self):
        """action_delay=1 + frame_skip=2 should compose correctly."""
        env, _, _ = make_env(action_delay=1, frame_skip=2)

        # Step 0: JUMP enqueued, NOOP executed (× 2 internal frames).
        env.step(ACTION_JUMP)
        assert env.trex_y == 0, "Delay=1: jump should not apply on step 0"

        # Step 1: NOOP enqueued, JUMP executed (× 2 internal frames).
        env.step(ACTION_NOOP)
        assert env.trex_y > 0, "Delay=1: jump should apply on step 1 (with frameskip=2)"
        env.close()

    def test_all_v2_params(self):
        """action_delay=1, frame_skip=2, clear_time_ms=3000 — smoke test."""
        env, obs, info = make_env(
            action_delay=1, frame_skip=2, clear_time_ms=3000,
        )
        assert obs.shape == (20,)
        assert env.observation_space.contains(obs)

        # Should survive many steps during the clear window.
        for _ in range(50):
            obs, _, terminated, truncated, _ = env.step(ACTION_NOOP)
            assert obs.shape == (20,)
            if terminated or truncated:
                pytest.fail("Should not terminate during clear window")
        env.close()

    def test_observation_space_unchanged_with_v2_params(self):
        """Observation & action spaces must remain the same regardless of v2 params."""
        env = DinoEnv(action_delay=3, frame_skip=4, clear_time_ms=2000)
        assert env.observation_space.shape == (20,)
        assert env.action_space.n == 3
        env.close()


# ===================================================================
# 7. endJump Velocity Cap Tests (Chromium trex.ts:483-520)
# ===================================================================

class TestEndJumpCap:
    """Spec §7 — maxJumpHeight / endJump velocity cap from Chromium."""

    def test_velocity_capped_above_max_jump_height(self):
        """Once trex_y exceeds MAX_JUMP_HEIGHT, upward vy is capped to DROP_VELOCITY."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.0
        # Trigger jump
        env._step_internal(1)
        # Step until above MAX_JUMP_HEIGHT
        while env.trex_y < MAX_JUMP_HEIGHT:
            env._step_internal(0)
        # At this point, vy should be capped
        assert env.trex_vy == pytest.approx(DROP_VELOCITY, abs=0.01), \
            f"vy should be ~{DROP_VELOCITY} above MAX_JUMP_HEIGHT, got {env.trex_vy}"
        env.close()

    def test_reached_min_height_set(self):
        """reached_min_height becomes True once trex_y >= MIN_JUMP_HEIGHT."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.0
        env._step_internal(1)
        assert not env.reached_min_height
        while env.trex_y < MIN_JUMP_HEIGHT:
            env._step_internal(0)
            if env.trex_y < MIN_JUMP_HEIGHT:
                assert not env.reached_min_height
        assert env.reached_min_height
        env.close()

    def test_peak_lower_than_uncapped(self):
        """The endJump cap must reduce peak height vs uncapped ballistic trajectory."""
        env = DinoEnv()
        env.reset()
        env.speed = 8.0
        # Compute uncapped peak
        vy = INITIAL_JUMP_VELOCITY + 8.0 / 10.0
        y = 0.0
        uncapped_peak = 0.0
        while True:
            y += vy
            vy -= GRAVITY
            uncapped_peak = max(uncapped_peak, y)
            if y <= 0:
                break
        # Run env jump
        env._step_internal(1)
        capped_peak = 0.0
        for _ in range(50):
            env._step_internal(0)
            capped_peak = max(capped_peak, env.trex_y)
            if not env.jumping:
                break
        assert capped_peak < uncapped_peak, \
            f"Capped peak {capped_peak:.1f} should be < uncapped {uncapped_peak:.1f}"
        env.close()

    def test_peak_approximately_matches_chrome(self):
        """At speed 7.6, peak should be ~83 (Chrome measured ~87 with rounding)."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.6
        env._step_internal(1)
        peak = 0.0
        for _ in range(50):
            env._step_internal(0)
            peak = max(peak, env.trex_y)
            if not env.jumping:
                break
        # Chrome peaks at ~87 (with Math.round), our float arithmetic gives ~83
        assert 78 < peak < 90, f"Peak {peak:.1f} should be ~83 (Chrome ~87)"
        env.close()

    def test_reached_min_height_resets_on_landing(self):
        """reached_min_height resets when the dino lands."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.0
        env._step_internal(1)
        # Jump until landing
        for _ in range(50):
            env._step_internal(0)
            if not env.jumping:
                break
        assert not env.reached_min_height
        env.close()

    def test_reached_min_height_resets_on_new_jump(self):
        """reached_min_height resets at the start of a new jump."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.0
        # First jump
        env._step_internal(1)
        for _ in range(50):
            env._step_internal(0)
            if not env.jumping:
                break
        # Second jump
        env._step_internal(1)
        assert not env.reached_min_height
        env.close()

    def test_speed_drop_bypasses_min_height_for_cap(self):
        """speed_drop should allow endJump cap even below MIN_JUMP_HEIGHT."""
        env = DinoEnv()
        env.reset()
        env.speed = 7.0
        # Jump then immediately duck (speed_drop)
        env._step_internal(1)
        initial_vy = env.trex_vy
        env._step_internal(2)  # duck in air => speed_drop = True
        assert env.speed_drop
        # speed_drop sets reached_min_height, so cap should apply
        # The fast gravity means vy may already be <= DROP_VELOCITY
        # after a few frames; verify cap activates within first few frames
        for _ in range(3):
            env._step_internal(2)
        # vy should be capped (or already below due to fast gravity)
        assert env.trex_vy <= DROP_VELOCITY + 0.01, \
            f"With speed_drop, vy should be capped at {DROP_VELOCITY}, got {env.trex_vy}"
        env.close()
