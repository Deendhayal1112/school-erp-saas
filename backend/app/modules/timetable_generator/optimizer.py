import copy
import logging
from typing import Any

from app.modules.timetable_generator.constraint_engine import ConstraintEngine

logger = logging.getLogger(__name__)


class TimetableOptimizer:
    """
    Greedy optimization tuner swapping period allocations to maximize soft constraint
    scores without violating hard constraints.
    """

    def __init__(self, constraint_engine: ConstraintEngine) -> None:
        self.constraint_engine = constraint_engine

    def optimize(
        self,
        schedule: list[dict[str, Any]],
        max_iterations: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Runs greedy hill-climbing search on the generated schedule.
        Iteratively swaps slots of compatible allocations to find higher scoring configurations.
        """
        current_schedule = copy.deepcopy(schedule)
        current_score = self.constraint_engine.calculate_score(current_schedule)
        logger.info(f"Starting schedule optimization. Initial score: {current_score}")

        improved = True
        iteration = 0

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            # Try swapping slots of two distinct allocations
            for i in range(len(current_schedule)):
                for j in range(i + 1, len(current_schedule)):
                    entry_a = current_schedule[i]
                    entry_b = current_schedule[j]

                    # Swap slots, days and rooms
                    new_a = copy.deepcopy(entry_a)
                    new_b = copy.deepcopy(entry_b)

                    new_a["working_day_id"], new_b["working_day_id"] = entry_b["working_day_id"], entry_a["working_day_id"]
                    new_a["time_slot_id"], new_b["time_slot_id"] = entry_b["time_slot_id"], entry_a["time_slot_id"]
                    new_a["room_id"], new_b["room_id"] = entry_b.get("room_id"), entry_a.get("room_id")

                    # Temp schedule without these two
                    temp_schedule = [e for idx, e in enumerate(current_schedule) if idx != i and idx != j]

                    # Validate both swapped candidates
                    if self.constraint_engine.is_valid_assignment(new_a, temp_schedule):
                        temp_schedule.append(new_a)
                        if self.constraint_engine.is_valid_assignment(new_b, temp_schedule):
                            temp_schedule.append(new_b)

                            # Calculate new score
                            new_score = self.constraint_engine.calculate_score(temp_schedule)
                            if new_score > current_score:
                                current_schedule = temp_schedule
                                current_score = new_score
                                improved = True
                                break
                            else:
                                # Revert
                                temp_schedule.pop()

                    if improved:
                        break
                if improved:
                    break

        logger.info(f"Schedule optimization complete in {iteration} iterations. Final score: {current_score}")
        return current_schedule
