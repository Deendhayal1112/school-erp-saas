from fastapi import APIRouter

from app.api.v1.academic_dashboard.router import router as academic_dashboard_router
from app.api.v1.academic_settings.router import router as academic_settings_router
from app.api.v1.academic_year.router import router as academic_year_router
from app.api.v1.admission.router import router as admission_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.class_subject_mapping.router import router as class_subject_router
from app.api.v1.curriculum.router import router as curriculum_router
from app.api.v1.department.router import router as department_router
from app.api.v1.designation.router import router as designation_router
from app.api.v1.employee.router import router as employee_router
from app.api.v1.employee_document.router import router as employee_document_router
from app.api.v1.experience.router import router as experience_router
from app.api.v1.guardian.router import router as guardian_router
from app.api.v1.leave.router import router as leave_router
from app.api.v1.qualification.router import router as qualification_router
from app.api.v1.section_management.router import router as section_router
from app.api.v1.staff_attendance.router import router as staff_attendance_router
from app.api.v1.student.router import router as student_router
from app.api.v1.student_assignment.router import router as student_assignment_router
from app.api.v1.student_dashboard.router import router as student_dashboard_router
from app.api.v1.student_documents.router import router as student_documents_router
from app.api.v1.student_medical.router import router as student_medical_router
from app.api.v1.student_progression.router import router as student_progression_router
from app.api.v1.subject_group.router import router as subject_group_router
from app.api.v1.subject_management.router import router as subject_router
from app.api.v1.teacher.router import router as teacher_router
from app.api.v1.term.router import router as term_router
from app.api.v1.teacher_dashboard.router import dashboard_router as teacher_dashboard_router
from app.api.v1.teacher_dashboard.router import reports_router as teacher_reports_router
from app.api.v1.academic_calendar.router import router as academic_calendar_router
from app.api.v1.time_slot.router import router as timeslot_router
from app.api.v1.room.router import router as room_router
from app.modules.auth.email.router import router as email_router
from app.modules.auth.password.router import router as password_router
from app.api.v1.teacher_subject_allocation.router import router as teacher_subject_allocation_router
from app.api.v1.class_timetable.router import router as class_timetable_router
from app.api.v1.teacher_timetable.router import router as teacher_timetable_router
from app.api.v1.timetable_generator.router import router as timetable_generator_router
from app.api.v1.timetable_conflict.router import router as timetable_conflict_router
from app.api.v1.timetable_adjustment.router import router as timetable_adjustment_router
from app.api.v1.timetable_dashboard.router import dashboard_router as timetable_dashboard_router
from app.api.v1.timetable_dashboard.router import reports_router as timetable_reports_router

# No /v1 prefix here — main.py mounts api_router under settings.API_V1_STR (/api/v1)
v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(password_router)
v1_router.include_router(email_router)
v1_router.include_router(student_router)
v1_router.include_router(guardian_router)
v1_router.include_router(admission_router)
v1_router.include_router(student_documents_router)
v1_router.include_router(student_medical_router)
v1_router.include_router(student_assignment_router)
v1_router.include_router(student_progression_router)
v1_router.include_router(student_dashboard_router)
v1_router.include_router(academic_year_router)
v1_router.include_router(term_router)
v1_router.include_router(section_router)
v1_router.include_router(subject_router)
v1_router.include_router(subject_group_router)
v1_router.include_router(class_subject_router)
v1_router.include_router(curriculum_router)
v1_router.include_router(academic_settings_router)
v1_router.include_router(academic_dashboard_router)
v1_router.include_router(department_router, prefix="/departments", tags=["Department"])
v1_router.include_router(
    designation_router, prefix="/designations", tags=["Designation"]
)
v1_router.include_router(employee_router, prefix="/employees", tags=["Employee"])
v1_router.include_router(
    employee_document_router, prefix="/employee-documents", tags=["Employee Document"]
)
v1_router.include_router(teacher_router, prefix="/teachers", tags=["Teacher"])
v1_router.include_router(
    qualification_router, prefix="/qualifications", tags=["Qualification"]
)
v1_router.include_router(experience_router, prefix="/experiences", tags=["Experience"])
v1_router.include_router(leave_router, prefix="/leaves", tags=["Leave"])
v1_router.include_router(
    staff_attendance_router, prefix="/attendance", tags=["Staff Attendance"]
)
v1_router.include_router(teacher_dashboard_router)
v1_router.include_router(teacher_reports_router)
v1_router.include_router(academic_calendar_router)
v1_router.include_router(timeslot_router)
v1_router.include_router(room_router)
v1_router.include_router(teacher_subject_allocation_router, prefix="/teacher-subject-allocations")
v1_router.include_router(class_timetable_router, prefix="/class-timetables")
v1_router.include_router(teacher_timetable_router, prefix="/teacher-timetables")
v1_router.include_router(timetable_generator_router, prefix="/timetable-generator")
v1_router.include_router(timetable_conflict_router, prefix="/timetable-conflicts")
v1_router.include_router(timetable_adjustment_router, prefix="/timetable")
v1_router.include_router(timetable_dashboard_router)
v1_router.include_router(timetable_reports_router)


