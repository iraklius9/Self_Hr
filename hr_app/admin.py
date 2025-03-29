from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import Employee, Department, LeaveRequest, TimeEntry, News, Notification
from django.utils.translation import gettext_lazy as _
from django import forms

# Get the custom User model
User = get_user_model()

# Only unregister if they are registered
if Group in admin.site._registry:
    admin.site.unregister(Group)

class EmployeeAdminForm(forms.ModelForm):
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=True)
    
    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'email', 'birth_date', 'gender', 
                  'department', 'salary', 'start_date']
    
    def save(self, commit=True):
        employee = super().save(commit=False)
        
        # Check if this is a new employee or an existing one
        if not employee.pk:
            # New employee: create a new user
            # Generate username from email if username is not used
            username = employee.email.split('@')[0]  # Simple way to generate username
            
            # Make username unique if it already exists
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,  # Auto-generated from email
                email=employee.email,
                password=self.cleaned_data['password'],
                first_name=employee.first_name,
                last_name=employee.last_name
            )
            employee.user = user
        else:
            # Existing employee: update the user info
            if employee.user:
                user = employee.user
                user.email = employee.email
                user.first_name = employee.first_name
                user.last_name = employee.last_name
                
                # Only set password if provided
                if self.cleaned_data.get('password'):
                    user.set_password(self.cleaned_data['password'])
                
                user.save()
        
        if commit:
            employee.save()
        
        return employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm
    
    list_display = [
        'first_name', 'last_name', 'email', 'department'
    ]
    
    list_filter = [
        'department'
    ]
    
    search_fields = [
        'first_name', 'last_name', 'email'
    ]
    
    fieldsets = [
        ('Personal Information', {
            'fields': ['first_name', 'last_name', 'email', 'password', 'birth_date', 'gender']
        }),
        ('Employment Information', {
            'fields': ['department', 'salary', 'start_date']
        }),
    ]

    def get_fieldsets(self, request, obj=None):
        # For editing existing objects, make password optional
        fieldsets = super().get_fieldsets(request, obj)
        if obj:  # If editing an existing object
            # Make password field not required for editing
            self.form.base_fields['password'].required = False
        return fieldsets

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

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'check_in', 'check_out', 'ip_address')
    list_filter = ('employee', 'check_in')
    search_fields = ('employee__first_name', 'employee__last_name')

@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'posted_by', 'posted_at')
    search_fields = ('title', 'content')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'read', 'created_at')
    list_filter = ('read',)
    search_fields = ('user__username', 'message') 