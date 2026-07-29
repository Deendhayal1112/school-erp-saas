# Cache TTL constants for staff attendance module

SHIFT_CACHE_TTL = 3600  # 1 hour — shifts rarely change
POLICY_CACHE_TTL = 3600  # 1 hour — policies rarely change
SUMMARY_CACHE_TTL = 300  # 5 minutes — summary is near-realtime
DEVICE_CACHE_TTL = 1800  # 30 minutes

# Attendance constraints
MAX_GRACE_MINUTES = 120
MAX_WORKING_HOURS = 24
MAX_OVERTIME_HOURS = 12
REGULARIZATION_WINDOW_DAYS = 30  # Days after which regularization is blocked
