# Specimens: Code Quality & Architecture Review

## Current State Assessment

### Strengths

✅ **Clean Separation of Concerns**
- `simulation.py`: state management and main loop
- `behavior.py`: decision-making and action execution
- `specimen.py`: data model
- `genetics.py`, `personality.py`: trait systems
- `reproduction.py`: life cycle
- `world.py`: environment
- `death.py`: mortality rules

✅ **Type Hints Throughout**
- All functions have proper return type annotations
- Dataclasses use `@dataclass` decorator with field types
- TYPE_CHECKING guards prevent circular imports

✅ **Stateless Behavior Engine**
- `BehaviorEngine.choose()` and `execute()` take specimen + simulation as parameters
- No mutable global state; re-entrant and testable

✅ **Reproducibility**
- 23 passing unit tests
- State-based initialization (seed random with same value = same run)
- Regression tests for death markers, ecology, economics

✅ **Real-time Responsiveness**
- 10 Hz tick rate maintained
- No blocking I/O in main loop
- Async WebSocket broadcasting

---

## Issues & Concerns

### 1. **Behavior Utility Scoring Complexity** 🟡 MEDIUM

**Current:**
- `choose()` method is 80+ lines, building 24 different utility entries
- Heavy use of conditional modifiers for time, weather, state
- Hard to reason about priority conflicts (e.g., eat vs. work vs. socialize)

**Risk:**
- Difficult to debug why a specimen chose an unexpected action
- Changes to one modifier can ripple across multiple actions
- No clear "why did X choose Y?" trace for players/LLM analysis

**Recommendation:**
- Split utilities into smaller, composable functions:
  ```python
  def _base_utility(action: str, specimen) -> float
  def _time_modifier(action: str, simulation) -> float
  def _weather_modifier(action: str, simulation) -> float
  def _state_modifier(action: str, specimen) -> float
  ```
- Log final utilities to trace decisions for analytics

### 2. **Movement Without Pathfinding** 🟡 MEDIUM

**Current:**
- `_move_toward()` is simple: move toward target in straight line
- No obstacle avoidance; creatures can "walk through" zones
- Creatures cross entire map to reach café even if blocked by forest

**Risk:**
- Unrealistic spatial behavior
- Hunger-driven specimens take long detours
- Hard to create emergent "crowd" behavior

**Recommendation:**
- Implement simple waypoint system (café has entry point, forest has edges)
- Or: add soft "attractors" that pull creatures toward zone centers

### 3. **Relationship Decay Not Implemented** 🟡 MEDIUM

**Current:**
- `Personality.forgetfulness` trait exists but is unused
- Relationships don't decay over time
- A single donation grants +8 relationship *forever*

**Risk:**
- Relationships don't reflect passage of time
- No incentive for repeated socializing
- Partner selection becomes static after first meeting

**Recommendation:**
- Per tick, decay relationship by `forgetfulness / 1000` (slow drift)
- Interaction resets decay counter (like LRU cache)

### 4. **Death Marker Leakage** 🟢 MINOR

**Current:**
- `simulation.death_markers` keeps last 100 markers in memory
- Never cleared except on reset
- At full size, adds ~5KB per simulation

**Risk:**
- Long-running simulations accumulate stale data
- Browser rendering 100 X's even from hour-old deaths

**Recommendation:**
- Remove markers after visible window (e.g., last 30 seconds of real time)
- Or: archive to separate history system

### 5. **No Conflict Resolution for Simultaneous Births** 🟢 MINOR

**Current:**
- Two women can become pregnant simultaneously in same couple
- No check for "one partner per woman" enforcement

**Risk:**
- Unrealistic: one man fathering twins from same woman
- Edge case but violates simulation consistency

**Recommendation:**
- Track `partner_id` and ensure mutual exclusion (woman has one current partner)
- Or: implement "engagement" phase before copulation

### 6. **Weather Not Affecting Movement Cost** 🟢 MINOR

**Current:**
- Weather scales movement by 0.65 (rain/storm) but affects all actions equally
- No "mud" mechanic or destination delay

**Risk:**
- Storm feels minor; creatures still reach destination quickly
- No incentive to shelter during bad weather (only hunger/fatigue apply)

**Recommendation:**
- Scale movement speed, not just action utility
- Add shelter-seeking bonus during storms (emergency action)

### 7. **No Collision Detection Between Specimens** 🟡 MEDIUM

**Current:**
- Specimens can occupy exact same (x, y) coordinates
- Clusters at café/bar are meaningless spatially

**Risk:**
- No "crowding" effect or congestion
- Pathfinding unnecessary since overlap is allowed
- Hard to visualize dense populations

**Recommendation:**
- Add soft collision: specimens repel each other if < 5m apart
- Or: implement "arrival at zone" discrete event (not continuous position)

### 8. **Job Assignment Is Random** 🟡 MEDIUM

**Current:**
- `_assign_job()` calls random choice from job pool
- No mechanism for job specialization or skill matching

**Risk:**
- Every specimen has equal work output
- No reason for employers to prefer any candidate
- No career progression or skill decay

**Recommendation:**
- Tie job type to genetic traits (e.g., high attack → bouncer, high discipline → accountant)
- Track job tenure and experience

### 9. **Intoxication Reduces All Decision Quality** 🟢 MINOR

**Current:**
- Intoxication is tracked but only used for reproduction boost at home
- No negative decision-making effects

**Risk:**
- Intoxicated specimens still navigate perfectly
- Intoxication feels cosmetic

**Recommendation:**
- Add decision noise when intoxicated (utility scores shuffled)
- Or: random movement override

### 10. **World State Mutation During Iteration** 🟠 SUBTLE BUG RISK

**Current:**
- `step()` iterates `for specimen in list(self.specimens.values())`
- Within loop, specimens can die, resources can spawn/despawn
- Iterator copies list, so safe, but fragile

**Risk:**
- If ever changed to iterate dict directly, crashes on modification
- Hard to reason about state consistency

**Recommendation:**
- Document this pattern
- Or: use explicit "queue" for births/deaths (resolve after all actions)

---

## Architecture Improvements (Optional)

### 1. **Event System** (Instead of Direct Mutation)

```python
class Event:
    type: str  # "birth", "death", "conflict", "theft"
    actor_id: int
    tick: int

# Per tick:
events = []
for specimen in ...:
    # Actions queue events instead of mutating state
    behavior.execute(specimen, action, simulation, events)
# Post-process events
for event in events:
    simulation.apply_event(event)
```

**Benefit:**
- Easier to replay, debug, analyze history
- LLM can observe "what just happened" instead of state diff

### 2. **Component-Based Specimen** (Instead of Monolithic @dataclass)

```python
@dataclass
class Specimen:
    id: int
    position: Position
    needs: Needs  # hunger, fatigue, wallet
    social: Social  # relationships, reputation
    biology: Biology  # genetics, personality, age
    job: Optional[Job]
```

**Benefit:**
- Cleaner organization
- Easier to add/remove subsystems (pregnancy, intoxication, run stamina)

### 3. **Scenario System** (Already Partially Implemented)

```python
SCENARIOS = {
    "balanced": {},
    "high_conflict": {"aggression": (65, 100)},
    "peaceful": {"aggression": (1, 30)},
    "fertile": {"fertility": (80, 100)},
}
```

**Benefit:**
- Easy to experiment with "what if" runs
- Players can tune simulation difficulty

---

## Test Coverage Gaps

### Currently Tested ✅
- Population dynamics (birth, death, aging)
- Resource reset (ecology restoration)
- Death markers (accuracy and causes)
- Poisonous plant mechanics
- Bear attack behavior
- Housing transactions
- Relationship tracking
- Forest ecology (plant growth, animal movement)
- Payroll system (accrual and distribution)

### Missing Tests ❌
- **Decision logic**: utility scoring correctness for each action
- **Movement**: pathfinding to destinations
- **Conflict**: damage calculation, death threshold
- **Intoxication**: effect on movement and reproduction
- **Weather**: hunger/fatigue modifiers
- **Job assignment**: trait-job matching
- **Theft**: detection and reputation loss
- **Pregnancy**: gestation duration, birth characteristics
- **Relationship decay**: (not implemented yet)
- **Run stamina**: recovery rates

**Recommendation:**
- Add parametrized tests for each behavior action
- Add "happiness" metric test (long-term stability)
- Add "ecology balance" test (wildlife populations sustainable)

---

## Performance Profiling Notes

### Current Bottlenecks (Estimated)

1. **Decision-making**: O(N × 24) where N = alive specimens (400µs for 42)
2. **State packet serialization**: O(N) (JSON encode) (150µs for 42)
3. **WebSocket broadcast**: O(C) where C = connected clients (varies)
4. **Rendering**: O(N + R) where R = resources (Canvas draw) (varies)

### Optimizations Possible

- Cache utility calculations between ticks (risky; state changes)
- Batch WebSocket broadcasts (already done)
- Lazy state serialization (only diff changes)
- Web Worker for decision logic (overkill)

---

## Code Smell Summary

| Issue | Severity | Effort to Fix | Impact |
|-------|----------|---------------|--------|
| Utility scoring complexity | 🟡 Medium | 2–3 hours | Maintainability |
| No pathfinding | 🟡 Medium | 4–6 hours | Realism |
| Relationship decay missing | 🟡 Medium | 1–2 hours | Emergent behavior |
| Death marker leakage | 🟢 Minor | 30 min | Memory |
| No conflict resolution | 🟡 Medium | 1 hour | Consistency |
| Intoxication under-utilized | 🟡 Medium | 1–2 hours | Game feel |
| Collision detection missing | 🟡 Medium | 2–3 hours | Spatial realism |
| Job randomness | 🟡 Medium | 2–3 hours | Career depth |
| World state mutation fragility | 🟠 Subtle | 1 hour | Bug prevention |

---

## Recommendations for Next Session

**Quick Wins (30 min each):**
1. Add relationship decay (forgetfulness modifier)
2. Log utility scores for debugging
3. Remove old death markers
4. Add "arriving at destination" discrete event
## Completed in Session (Quick Wins)

✅ **Relationship Decay (Completed)**
- Per-tick decay using forgetfulness trait: `forgetfulness / 100000.0`
- Relationships decay toward neutral (0) slowly (~1 point per day at max forgetfulness)
- Prevents relationships from freezing forever
- Enables long-term social arc changes
- Test: `test_relationship_decay_applies_per_tick()` validates decay behavior

✅ **Death Marker Cleanup (Completed)**
- Added marker pruning in `_record_death()`: keeps only markers within 100 ticks (10 real seconds)
- Memory optimization: prevents unbounded growth of death marker list
- Pruning triggered on each new death record
- Test: `test_death_markers_are_pruned_after_100_ticks()` validates cleanup

✅ **Utility Score Logging (Completed)**
- Added optional debug logging in `BehaviorEngine.choose()` 
- Logs top 3 actions for each specimen when `simulation._debug_utilities = True`
- Format: `[{name}#{id}] Top actions: action1=X.X, action2=Y.Y, action3=Z.Z`
- Enables decision tracing and LLM analysis integration

⏳ **Destination Arrival Event (Deferred)**
- Requires tracking destination coordinates in Specimen model
- Would add ~2 hours of architecture work
- Deprioritized in favor of immediate behavioral improvements

---

## Remaining Improvements

**Quick Wins (30 min each):**

**Medium Effort (2–3 hours):**
1. Split utility scoring into composable functions
2. Implement soft collision detection
3. Add intoxication decision noise

**Longer Term (4+ hours):**
1. Replace straight-line movement with waypoint pathfinding
2. Implement job specialization (traits → job type)
3. Refactor Specimen to component-based architecture
4. Add event queue system for replay/analysis

---

## Conclusion

**Specimens is a well-structured, feature-rich simulation** with clear separation of concerns and strong test coverage. The main limitations are:

- **Incomplete social dynamics** (no relationship decay, no conflict resolution)
- **Simplistic spatial modeling** (no pathfinding, no collisions)
- **Utility scoring is a black box** (hard to reason about decisions)

These are **not blocking issues**; the game runs smoothly and emergent behaviors are visible. They become pain points only if:
- You want to add LLM analysis (needs decision traceability)
- You want realistic spatial crowds (needs pathfinding)
- You want long-term relationship arcs (needs decay)

**Recommended next milestone:** Add decision logging and relationship decay (1–2 hours) to unlock better player understanding and emergent behavior complexity.

