import logging
import time
from typing import Any

from app.modules.timetable_generator.constants import MAX_BACKTRACK_DEPTH
from app.modules.timetable_generator.constraint_engine import ConstraintEngine

logger = logging.getLogger(__name__)


class TimetableScheduler:
    """
    Backtracking schedule solver utilizing MRV (Minimum Remaining Values) and
    constraint-propagation heuristics to generate conflict-free allocations.
    """

    def __init__(
        self,
        constraint_engine: ConstraintEngine,
        available_slots: list[tuple[Any, Any]],  # list of (working_day_id, time_slot_id)
        rooms: list[Any],  # list of room_id
    ) -> None:
        self.constraint_engine = constraint_engine
        self.available_slots = available_slots
        self.rooms = rooms
        self.iterations = 0

    def solve(
        self,
        required_allocations: list[dict[str, Any]],  # List of dicts representing period requirements
        timeout_seconds: float = 60.0,
    ) -> list[dict[str, Any]] | None:
        """
        Runs backtracking solver to find a valid assignment for all required allocations.
        Returns a list of scheduled entries if successful, or None if no solution was found.
        """
        self.iterations = 0
        start_time = time.time()

        # Heuristic: Sort required allocations by MRV-inspired sorting (e.g. teachers with fewer available slots first)
        # For simplicity, we can sort by teacher weekly limit (descending) or total weekly allocations required
        # so that high workload/rigid allocations are handled first.
        required_allocations_sorted = sorted(
            required_allocations,
            key=lambda x: self.constraint_engine.teacher_workloads.get(x["teacher_id"], {}).get("max_weekly", 24),
            reverse=True,
        )

        schedule: list[dict[str, Any]] = []
        success = self._backtrack(required_allocations_sorted, 0, schedule, start_time, timeout_seconds)
        if success:
            return schedule
        return None

    def _backtrack(
        self,
        unassigned: list[dict[str, Any]],
        index: int,
        schedule: list[dict[str, Any]],
        start_time: float,
        timeout: float,
    ) -> bool:
        self.iterations += 1

        # Check recursion base case: all periods scheduled
        if index >= len(unassigned):
            return True

        # Check performance constraints: abort if timeout exceeded or iterations exceed limit
        if time.time() - start_time > timeout:
            logger.warning("Timetable scheduler execution timed out.")
            return False
        if self.iterations > MAX_BACKTRACK_DEPTH:
            logger.warning("Timetable scheduler exceeded max backtracking depth.")
            return False

        current_var = unassigned[index]
        teacher_id = current_var["teacher_id"]
        subject_id = current_var["subject_id"]
        class_id = current_var["class_id"]
        section_id = current_var["section_id"]
        lesson_type = current_var["lesson_type"]

        # Order values: Preferred room first, then others
        pref_room = self.constraint_engine.preferred_rooms.get((teacher_id, subject_id))
        ordered_rooms = []
        if pref_room and pref_room in self.rooms:
            ordered_rooms.append(pref_room)
        for r in self.rooms:
            if r != pref_room:
                ordered_rooms.append(r)

        # Loop over available days and slots
        # For performance, we can randomize or shuffle the slots or order them by slot occupancy.
        # Here we iterate directly.
        for day_id, slot_id in self.available_slots:
            for room_id in ordered_rooms:
                candidate = {
                    "teacher_id": teacher_id,
                    "subject_id": subject_id,
                    "class_id": class_id,
                    "section_id": section_id,
                    "working_day_id": day_id,
                    "time_slot_id": slot_id,
                    "room_id": room_id,
                    "lesson_type": lesson_type,
                }

                if self.constraint_engine.is_valid_assignment(candidate, schedule):
                    # Place assignment
                    schedule.append(candidate)

                    # Recurse
                    if self._backtrack(unassigned, index + 1, schedule, start_time, timeout):
                        return True

                    # Backtrack
                    schedule.pop()

        return False
