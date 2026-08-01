"""
Constants for the Timetable Adjustment & Teacher Substitution module.
"""

# Cache TTLs (seconds)
PENDING_ADJUSTMENTS_TTL = 120      # 2 minutes — high churn
APPROVED_ADJUSTMENTS_TTL = 300     # 5 minutes
SUBSTITUTION_SUGGESTIONS_TTL = 60  # 1 minute
TEACHER_AVAILABILITY_TTL = 180     # 3 minutes

# Cache key templates
PENDING_ADJUSTMENTS_KEY = "timetable_adj:pending:{school_id}"
APPROVED_ADJUSTMENTS_KEY = "timetable_adj:approved:{school_id}"
SUGGESTIONS_KEY = "timetable_adj:suggestions:{school_id}:{entry_id}"
TEACHER_AVAIL_KEY = "timetable_adj:teacher_avail:{school_id}:{teacher_id}"

# Business rules
MAX_ADJUSTMENT_DURATION_DAYS = 365   # Max effective period for an adjustment
MAX_CONCURRENT_SUBSTITUTIONS = 10    # Max active substitutions per teacher per week
MAX_SUGGESTION_RESULTS = 5           # Max substitute suggestions to return
