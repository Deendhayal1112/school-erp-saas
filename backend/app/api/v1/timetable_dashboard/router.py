"""
Re-exports the routers from the timetable_dashboard module.
"""

from app.modules.timetable_dashboard.router import dashboard_router, reports_router

__all__ = ["dashboard_router", "reports_router"]
