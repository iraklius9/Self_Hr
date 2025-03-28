from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from .models import Employee, Department, LeaveRequest, Role, TimeLog
from django.utils.translation import gettext_lazy as _

# Only unregister if they are registered
if User in admin.site._registry:
    admin.site.unregister(User)
if Group in admin.site._registry:
    admin.site.unregister(Group)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'job_title', 'department', 'start_date')
    list_filter = ('department', 'job_title')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('last_name', 'first_name')
    
    fieldsets = (
        (_('პირადი ინფორმაცია'), {
            'fields': ('user', 'first_name', 'last_name', 'email', 'phone')
        }),
        (_('სამსახურის ინფორმაცია'), {
            'fields': ('department', 'job_title', 'start_date')
        }),
    )

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = _('სრული სახელი')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_employee_count')
    search_fields = ('name',)

    def get_employee_count(self, obj):
        return obj.employees.count()
    get_employee_count.short_description = _('თანამშრომლების რაოდენობა')

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'leave_type')
    search_fields = ('employee__first_name', 'employee__last_name')
    ordering = ('-created_at',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')

@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'check_in', 'check_out', 'get_duration', 'ip_address')
    list_filter = ('employee', 'check_in')
    search_fields = ('employee__first_name', 'employee__last_name', 'ip_address')
    date_hierarchy = 'check_in'
    ordering = ('-check_in',)
    
    def get_duration(self, obj):
        if obj.check_in and obj.check_out:
            duration = obj.check_out - obj.check_in
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours}:{minutes:02d}"
        return "-"
    get_duration.short_description = "ხანგრძლივობა"

    fieldsets = (
        ('თანამშრომლის ინფორმაცია', {
            'fields': ('employee',)
        }),
        ('დროის ინფორმაცია', {
            'fields': ('check_in', 'check_out')
        }),
        ('ტექნიკური ინფორმაცია', {
            'fields': ('ip_address',),
            'classes': ('collapse',)
        }),
    ) 