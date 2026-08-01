# Timetable Generation Configuration Constants

MAX_BACKTRACK_DEPTH = 5000
GENERATION_TIMEOUT_SECONDS = 60.0

# Penalties/Rewards for Soft Constraint Scoring
SOFT_CONSTRAINT_WEIGHTS = {
    "preferred_room": 10,
    "preferred_teacher": 5,
    "balanced_workload": 8,
    "minimum_gaps": 6,
    "consecutive_limit_reward": 4,
}
