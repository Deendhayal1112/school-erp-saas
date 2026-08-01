import uuid
from typing import Any


class ConstraintEngine:
    """
    Validation engine enforcing hard constraints and calculating soft constraint scores
    for automatic timetable generation.
    """

    def __init__(
        self,
        teacher_availabilities: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], str],  # (teacher_id, day_id, slot_id) -> status
        teacher_workloads: dict[uuid.UUID, dict[str, int]],  # teacher_id -> limits (max_weekly, daily_limit, consecutive_limit)
        room_capacities: dict[uuid.UUID, int],  # room_id -> capacity
        section_capacities: dict[uuid.UUID, int],  # section_id -> capacity
        preferred_rooms: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID],  # (teacher_id, subject_id) -> preferred room_id
        time_slot_orders: dict[uuid.UUID, int],  # slot_id -> display_order
    ) -> None:
        self.teacher_availabilities = teacher_availabilities
        self.teacher_workloads = teacher_workloads
        self.room_capacities = room_capacities
        self.section_capacities = section_capacities
        self.preferred_rooms = preferred_rooms
        self.time_slot_orders = time_slot_orders

    # --- Hard Constraints Check ---

    def is_valid_assignment(
        self,
        assignment: dict[str, Any],  # current candidate assignment
        current_schedule: list[dict[str, Any]],  # already scheduled assignments
    ) -> bool:
        """
        Runs all hard constraints checks on a candidate assignment.
        Returns True if candidate satisfies all constraints, False otherwise.
        """
        teacher_id = assignment["teacher_id"]
        working_day_id = assignment["working_day_id"]
        time_slot_id = assignment["time_slot_id"]
        class_id = assignment["class_id"]
        section_id = assignment["section_id"]
        subject_id = assignment["subject_id"]
        room_id = assignment.get("room_id")

        # 1. Teacher cannot teach two classes at the same time (no teacher double booking)
        for entry in current_schedule:
            if (
                entry["working_day_id"] == working_day_id
                and entry["time_slot_id"] == time_slot_id
                and entry["teacher_id"] == teacher_id
            ):
                return False

        # 2. Class/Section cannot have two subjects at the same time (no class double booking)
        for entry in current_schedule:
            if (
                entry["working_day_id"] == working_day_id
                and entry["time_slot_id"] == time_slot_id
                and entry["class_id"] == class_id
                and entry["section_id"] == section_id
            ):
                return False

        # 3. Room cannot have two classes at the same time (no room double booking)
        if room_id:
            for entry in current_schedule:
                if (
                    entry["working_day_id"] == working_day_id
                    and entry["time_slot_id"] == time_slot_id
                    and entry.get("room_id") == room_id
                ):
                    return False

        # 4. Teacher availability check
        avail_status = self.teacher_availabilities.get((teacher_id, working_day_id, time_slot_id))
        if avail_status == "UNAVAILABLE":
            return False

        # 5. Teacher workload limit (weekly check)
        limits = self.teacher_workloads.get(teacher_id, {})
        max_weekly = limits.get("max_weekly", 24)
        teacher_weekly_count = sum(1 for e in current_schedule if e["teacher_id"] == teacher_id)
        if teacher_weekly_count >= max_weekly:
            return False

        # 6. Teacher daily limit
        max_daily = limits.get("daily_limit", 6)
        teacher_daily_count = sum(
            1 for e in current_schedule if e["teacher_id"] == teacher_id and e["working_day_id"] == working_day_id
        )
        if teacher_daily_count >= max_daily:
            return False

        # 7. Teacher consecutive period limit
        max_consecutive = limits.get("consecutive_period_limit", 3)
        if max_consecutive > 0:
            # Check slots order for this day
            slots_on_day = [
                e for e in current_schedule if e["teacher_id"] == teacher_id and e["working_day_id"] == working_day_id
            ]
            # Add current candidate to list
            slots_on_day.append(assignment)
            # Sort by slot display order
            slots_on_day.sort(key=lambda x: self.time_slot_orders.get(x["time_slot_id"], 0))

            consec_count = 0
            prev_order = -100
            for e in slots_on_day:
                order = self.time_slot_orders.get(e["time_slot_id"], 0)
                if order == prev_order + 1:
                    consec_count += 1
                else:
                    consec_count = 1
                if consec_count > max_consecutive:
                    return False
                prev_order = order

        # 8. Room capacity validation
        if room_id:
            room_cap = self.room_capacities.get(room_id, 0)
            sect_cap = self.section_capacities.get(section_id, 0)
            if room_cap < sect_cap:
                return False

        # 9. Subject daily limit (e.g. max 2 periods of same subject per day for a section)
        subject_daily_count = sum(
            1
            for e in current_schedule
            if e["section_id"] == section_id
            and e["subject_id"] == subject_id
            and e["working_day_id"] == working_day_id
        )
        if subject_daily_count >= 2:
            return False

        return True

    # --- Soft Constraints & Scoring ---

    def calculate_score(self, schedule: list[dict[str, Any]]) -> float:
        """
        Calculates optimization score for a complete or partial schedule.
        Larger scores represent higher quality schedules adhering to soft constraints.
        """
        score = 0.0

        # Group schedule by teacher and working_day to check gaps/consecutive limits
        teacher_day_schedules: dict[tuple[uuid.UUID, uuid.UUID], list[dict[str, Any]]] = {}
        for entry in schedule:
            key = (entry["teacher_id"], entry["working_day_id"])
            if key not in teacher_day_schedules:
                teacher_day_schedules[key] = []
            teacher_day_schedules[key].append(entry)

        for (teacher_id, _day_id), day_entries in teacher_day_schedules.items():
            # Sort by display order
            day_entries.sort(key=lambda x: self.time_slot_orders.get(x["time_slot_id"], 0))

            # 1. Avoid Gaps (penalize if gap order difference is > 1 but has periods on both sides)
            for i in range(len(day_entries) - 1):
                order_current = self.time_slot_orders.get(day_entries[i]["time_slot_id"], 0)
                order_next = self.time_slot_orders.get(day_entries[i + 1]["time_slot_id"], 0)
                gap = order_next - order_current - 1
                if gap > 0:
                    # Penalize gaps: longer gaps have larger penalty
                    score -= gap * 6.0

            # 2. Balanced Workload (consecutive teaching reward)
            # Give a reward (+4) if consecutive periods <= consecutive_limit
            limits = self.teacher_workloads.get(teacher_id, {})
            max_consec = limits.get("consecutive_period_limit", 3)
            consec_count = 0
            prev_order = -100
            for e in day_entries:
                order = self.time_slot_orders.get(e["time_slot_id"], 0)
                if order == prev_order + 1:
                    consec_count += 1
                else:
                    consec_count = 1
                if consec_count <= max_consec:
                    score += 4.0
                prev_order = order

        # 3. Preferred Rooms (+10 reward per allocation matching preferred room)
        for entry in schedule:
            teacher_id = entry["teacher_id"]
            subject_id = entry["subject_id"]
            room_id = entry.get("room_id")
            pref_room = self.preferred_rooms.get((teacher_id, subject_id))
            if pref_room and room_id == pref_room:
                score += 10.0

        return score
