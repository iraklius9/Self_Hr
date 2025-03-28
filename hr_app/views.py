from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse, HttpResponse
import math
import requests
import ipaddress
import csv
from django.core.mail import send_mail
import random
import string
from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.db.models import Sum
from django.db.models.functions import TruncDate

from .models import (
    Employee, Department, TimeEntry, LeaveRequest, 
    News, Notification, Role, LocationLog, TimeLog
)
from .forms import (
    EmployeeForm, EmployeeUpdateForm, DepartmentForm, TimeEntryForm,
    LeaveRequestForm, LeaveRequestUpdateForm, NewsForm, RoleForm,
    EmployeeSearchForm, CustomAuthenticationForm,
    UserSignupForm
)

# Authentication Views
from django.contrib.auth.views import LoginView, LogoutView

class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure password reset URL is not in context
        if 'password_reset_url' in context:
            del context['password_reset_url']
        return context

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')
    http_method_names = ['get', 'post']  # Allow both GET and POST methods
    
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, _("წარმატებით გამოხვედით სისტემიდან!"))
        return redirect('login')

# Dashboard View
@login_required
def dashboard(request):
    if not hasattr(request.user, 'employee_profile'):
        messages.warning(request, _("თქვენ არ გაქვთ თანამშრომლის პროფილი. დაუკავშირდით ადმინისტრატორს."))
        return render(request, 'hr_app/dashboard.html')
    
    employee = request.user.employee_profile
    context = {
        'employee': employee,
        'time_entries': TimeEntry.objects.filter(employee=employee).order_by('-date')[:5],
        'leave_requests': LeaveRequest.objects.filter(employee=employee).order_by('-submitted_at')[:5],
        'news': News.objects.all().order_by('-posted_at')[:3],
        'notifications': Notification.objects.filter(user=request.user, read=False)[:5],
    }
    
    if hasattr(request.user, 'role') and request.user.role.role in ['admin', 'hr_manager']:
        context.update({
            'total_employees': Employee.objects.count(),
            'pending_leaves': LeaveRequest.objects.filter(status='pending').count(),
            'departments': Department.objects.all(),
        })
    
    return render(request, 'hr_app/dashboard.html', context)

# Employee Views
class EmployeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Employee
    template_name = 'hr_app/employee/list.html'
    context_object_name = 'employees'
    paginate_by = 10
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EmployeeSearchForm(self.request.GET)
        return context

class EmployeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Employee
    template_name = 'hr_app/employee/detail.html'
    
    def test_func(self):
        employee = self.get_object()
        return (hasattr(self.request.user, 'role') and 
                self.request.user.role.role in ['admin', 'hr_manager']) or \
               self.request.user == employee.user

class EmployeeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Employee
    template_name = 'hr_app/employee/form.html'
    fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'job_title', 'start_date']
    success_url = reverse_lazy('employee-list')
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def form_valid(self, form):
        messages.success(self.request, "თანამშრომელი წარმატებით დაემატა")
        return super().form_valid(form)

class EmployeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr_app/employee/form.html'
    
    def test_func(self):
        return (self.request.user.role.role in ['admin', 'hr_manager'] or 
                self.request.user.employee_profile.id == self.get_object().id)

    def get_success_url(self):
        return reverse_lazy('employee-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("თანამშრომლის პროფილი წარმატებით განახლდა"))
        return response

class EmployeeDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Employee
    template_name = 'hr_app/employee/delete.html'
    success_url = reverse_lazy('employee-list')
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _("თანამშრომელი წარმატებით წაიშალა"))
        return super().delete(request, *args, **kwargs)

# Leave Request Views
class LeaveRequestListView(LoginRequiredMixin, ListView):
    model = LeaveRequest
    template_name = 'hr_app/leave_request/list.html'
    context_object_name = 'leave_requests'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.role.role in ['admin', 'hr_manager']:
            # Admins and HR managers see all requests
            return LeaveRequest.objects.all().order_by('-created_at')
        # Regular employees see only their requests
        return LeaveRequest.objects.filter(employee=self.request.user.employee_profile).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = self.request.user.role.role in ['admin', 'hr_manager']
        return context

class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    model = LeaveRequest
    template_name = 'hr_app/leave_request/form.html'
    form_class = LeaveRequestForm
    success_url = reverse_lazy('leave-request-list')

    def form_valid(self, form):
        form.instance.employee = self.request.user.employee_profile
        form.instance.status = 'pending'
        messages.success(self.request, _("შვებულების მოთხოვნა წარმატებით გაიგზავნა"))
        return super().form_valid(form)

@login_required
def leave_request_update(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if not (hasattr(request.user, 'role') and request.user.role.role in ['admin', 'hr_manager']):
        messages.error(request, _("თქვენ არ გაქვთ უფლება შეცვალოთ შვებულების სტატუსი!"))
        return redirect('leave-list')
    
    if request.method == 'POST':
        form = LeaveRequestUpdateForm(request.POST, instance=leave_request)
        if form.is_valid():
            form.save()
            messages.success(request, _("შვებულების სტატუსი განახლდა!"))
            return redirect('leave-list')
    else:
        form = LeaveRequestUpdateForm(instance=leave_request)
    
    return render(request, 'hr_app/leave/update_form.html', {'form': form, 'leave_request': leave_request})

class LeaveRequestDetailView(LoginRequiredMixin, DetailView):
    model = LeaveRequest
    template_name = 'hr_app/leave_detail.html'
    context_object_name = 'leave_request'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Leave Request Details'
        return context

    def get_queryset(self):
        # Employees can only see their own leave requests
        # HR managers and admins can see all
        if self.request.user.role == 'employee':
            return LeaveRequest.objects.filter(employee__user=self.request.user)
        return LeaveRequest.objects.all()

# Time Entry Views
class TimeEntryListView(LoginRequiredMixin, ListView):
    model = TimeEntry
    template_name = 'hr_app/time/list.html'
    context_object_name = 'time_entries'
    paginate_by = 10
    
    def get_queryset(self):
        if hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']:
            return TimeEntry.objects.all().order_by('-date')
        return TimeEntry.objects.filter(employee__user=self.request.user).order_by('-date')

class TimeEntryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'hr_app/time/form.html'
    success_url = reverse_lazy('time-list')
    
    def test_func(self):
        return hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']
    
    def form_valid(self, form):
        messages.success(self.request, _("დროის ჩანაწერი წარმატებით დაემატა!"))
        return super().form_valid(form)

# News Views
class NewsListView(LoginRequiredMixin, ListView):
    model = News
    template_name = 'hr_app/news/list.html'
    context_object_name = 'news_list'
    paginate_by = 10

class NewsCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = News
    template_name = 'hr_app/news/form.html'
    fields = ['title', 'content']
    success_url = reverse_lazy('news-list')
    
    def test_func(self):
        return hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']
    
    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        return super().form_valid(form)

# Notification Views
@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read = True
    notification.save()
    return JsonResponse({'status': 'success'})

# Department Views
class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = 'hr_app/department/list.html'
    context_object_name = 'departments'

class DepartmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'hr_app/department/form.html'
    success_url = reverse_lazy('department-list')
    
    def test_func(self):
        return hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']
    
    def form_valid(self, form):
        messages.success(self.request, _("დეპარტამენტი წარმატებით დაემატა!"))
        return super().form_valid(form)

class DepartmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'hr_app/department/form.html'
    success_url = reverse_lazy('department-list')
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def form_valid(self, form):
        messages.success(self.request, _("დეპარტამენტი წარმატებით განახლდა!"))
        return super().form_valid(form)

class DepartmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Department
    template_name = 'hr_app/department/delete.html'
    success_url = reverse_lazy('department-list')
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _("დეპარტამენტი წარმატებით წაიშალა"))
        return super().delete(request, *args, **kwargs)

def export_time_entries(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="time_entries.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['თანამშრომელი', 'თარიღი', 'საათები', 'ზეგანაკვეთური'])
    
    entries = TimeEntry.objects.select_related('employee')
    for entry in entries:
        writer.writerow([
            entry.employee.get_full_name(),
            entry.date,
            entry.hours_worked,
            entry.overtime
        ])
    
    return response

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@login_required
def two_factor_auth(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        stored_otp = request.session.get('otp')
        
        if otp == stored_otp:
            request.session['verified'] = True
            return redirect(request.session.get('next', 'dashboard'))
        else:
            messages.error(request, 'არასწორი კოდი. სცადეთ თავიდან.')
    
    # Generate OTP
    otp = generate_otp()
    request.session['otp'] = otp
    
    # Send OTP via email
    send_mail(
        'ორფაქტორიანი ავთენტიფიკაციის კოდი',
        f'თქვენი კოდია: {otp}',
        'noreply@hrms.com',
        [request.user.email],
        fail_silently=False,
    )
    
    return render(request, 'hr_app/auth/two_factor.html')

# Add these views
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'hr_app/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['unread_notifications'] = user.notifications.filter(read=False)
        context['recent_news'] = News.objects.all()[:5]
        
        if hasattr(user, 'role') and user.role.role in ['admin', 'hr_manager']:
            context['total_employees'] = Employee.objects.count()
            context['pending_leaves'] = LeaveRequest.objects.filter(status='pending').count()
            context['active_employees'] = TimeLog.objects.filter(
                check_in__date=timezone.now().date(),
                check_out__isnull=True
            ).count()
        
        if hasattr(user, 'employee_profile'):
            context['leave_balance'] = user.employee_profile.vacation_days_left
            context['recent_time_logs'] = TimeLog.objects.filter(
                employee=user.employee_profile
            ).order_by('-check_in')[:5]
            context['pending_requests'] = LeaveRequest.objects.filter(
                employee=user.employee_profile,
                status='pending'
            )
        
        return context

class LeaveRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'hr_app/leave/form.html'
    success_url = reverse_lazy('leave-list')

    def test_func(self):
        # Only HR managers and admins can update leave requests
        if not hasattr(self.request.user, 'role'):
            return False
        return self.request.user.role.role in ['admin', 'hr_manager']

    def form_valid(self, form):
        messages.success(self.request, _("შვებულების მოთხოვნა წარმატებით განახლდა!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('შვებულების მოთხოვნის განახლება')
        context['submit_text'] = _('განახლება')
        return context 

@login_required
def check_notifications(request):
    """
    AJAX endpoint to check for new notifications
    """
    unread_count = Notification.objects.filter(
        user=request.user,
        read=False
    ).count()
    
    notifications = Notification.objects.filter(
        user=request.user,
        read=False
    ).order_by('-created_at')[:5]
    
    notifications_data = [{
        'id': notification.id,
        'message': notification.message,
        'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
        'url': notification.url if hasattr(notification, 'url') else None
    } for notification in notifications]
    
    return JsonResponse({
        'unread_count': unread_count,
        'notifications': notifications_data
    })

class SignupView(CreateView):
    template_name = 'registration/signup.html'
    form_class = UserSignupForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        # First save the user
        user = form.save()
        
        try:
            # Get or create role for the user
            role, created = Role.objects.get_or_create(
                user=user,
                defaults={'role': 'employee'}
            )
            if not created:
                role.role = 'employee'
                role.save()
            
            # Create employee profile with first_name and last_name
            Employee.objects.create(
                user=user,
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
                email=form.cleaned_data['email'],
                start_date=timezone.now().date(),
                job_title='თანამშრომელი'
            )
            
            messages.success(self.request, _("რეგისტრაცია წარმატებით დასრულდა. გთხოვთ შეხვიდეთ სისტემაში."))
            return redirect(self.success_url)
            
        except Exception as e:
            user.delete()
            messages.error(self.request, _("რეგისტრაციის დროს მოხდა შეცდომა. გთხოვთ სცადოთ თავიდან."))
            return redirect('signup')

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'hr_app/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_employees'] = Employee.objects.count()
        context['pending_leaves'] = LeaveRequest.objects.filter(status='pending').count()
        context['departments'] = Department.objects.all()
        context['recent_leaves'] = LeaveRequest.objects.order_by('-submitted_at')[:5]
        return context 

class LeaveRequestUpdateStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def post(self, request, pk):
        leave_request = get_object_or_404(LeaveRequest, pk=pk)
        status = request.POST.get('status')
        
        if status in ['approved', 'rejected']:
            leave_request.status = status
            leave_request.save()
            
            status_display = _("დამტკიცებულია") if status == 'approved' else _("უარყოფილია")
            messages.success(request, _(f"შვებულების მოთხოვნა {status_display}"))
        
        return redirect('leave-request-list')

class TimeTrackingView(LoginRequiredMixin, View):
    def get(self, request):
        employee = request.user.employee_profile
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get date range from query parameters, default to last 7 days
        days = int(request.GET.get('days', 7))
        start_date = today_start - timedelta(days=days)
        
        # Get current log
        current_log = TimeLog.objects.filter(
            employee=employee,
            check_in__gte=today_start,
            check_in__lte=today_end,
            check_out__isnull=True
        ).first()
        
        # Get today's logs
        today_logs = TimeLog.objects.filter(
            employee=employee,
            check_in__gte=today_start,
            check_in__lte=today_end
        ).order_by('-check_in')
        
        # Get historical logs grouped by date
        historical_logs = TimeLog.objects.filter(
            employee=employee,
            check_in__gte=start_date,
            check_in__lt=today_start
        ).annotate(
            date=TruncDate('check_in')
        ).order_by('-date', '-check_in')
        
        # For admins/managers, get all employees' logs
        if hasattr(request.user, 'role') and request.user.role.role in ['admin', 'hr_manager']:
            all_employees_current = TimeLog.objects.filter(
                check_in__gte=today_start,
                check_in__lte=today_end
            ).select_related('employee').order_by('employee__first_name', '-check_in')
            
            # Group logs by employee
            employees_logs = {}
            for log in all_employees_current:
                if log.employee not in employees_logs:
                    employees_logs[log.employee] = []
                employees_logs[log.employee].append(log)
                
            # Get historical data for all employees
            all_employees_historical = TimeLog.objects.filter(
                check_in__gte=start_date,
                check_in__lt=today_start
            ).select_related('employee').annotate(
                date=TruncDate('check_in')
            ).order_by('employee__first_name', '-date', '-check_in')
            
            employees_historical = {}
            for log in all_employees_historical:
                if log.employee not in employees_historical:
                    employees_historical[log.employee] = {}
                if log.date not in employees_historical[log.employee]:
                    employees_historical[log.employee][log.date] = []
                employees_historical[log.employee][log.date].append(log)
        else:
            employees_logs = None
            employees_historical = None

        context = {
            'current_log': current_log,
            'today_logs': today_logs,
            'historical_logs': historical_logs,
            'employees_logs': employees_logs,
            'employees_historical': employees_historical,
            'is_admin': request.user.role.role in ['admin', 'hr_manager'] if hasattr(request.user, 'role') else False,
            'is_in_office': True,  # Always allow for development
            'client_ip': self.get_client_ip(request),
            'selected_days': days,
        }
        return render(request, 'hr_app/time_tracking.html', context)

    def post(self, request):
        print("POST request received")
        action = request.POST.get('action')
        employee = request.user.employee_profile
        client_ip = self.get_client_ip(request)
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        print(f"Action: {action}, Employee: {employee}, IP: {client_ip}")

        try:
            # Get active session
            active_session = TimeLog.objects.filter(
                employee=employee,
                check_in__gte=today_start,
                check_in__lte=today_end,
                check_out__isnull=True
            ).first()
            
            print(f"Active session found: {active_session}")

            if action == 'check_in':
                if active_session:
                    messages.error(request, _("თქვენ უკვე დაფიქსირებული ხართ. ჯერ დაასრულეთ მიმდინარე სესია."))
                else:
                    new_log = TimeLog.objects.create(
                        employee=employee,
                        check_in=now,
                        ip_address=client_ip
                    )
                    print(f"Created new log: {new_log}")
                    messages.success(request, _("სამუშაო დღე დაწყებულია"))

            elif action == 'check_out':
                if active_session:
                    active_session.check_out = now
                    active_session.save()
                    print(f"Updated log with checkout: {active_session}")
                    messages.success(request, _("სამუშაო დღე დასრულებულია"))
                else:
                    messages.error(request, _("აქტიური სამუშაო სესია ვერ მოიძებნა"))

        except Exception as e:
            print(f"Error occurred: {str(e)}")
            messages.error(request, str(e))

        return redirect('time-tracking')

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip 

class OrganizationalStructureView(LoginRequiredMixin, TemplateView):
    template_name = 'hr_app/organization/structure.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departments = Department.objects.prefetch_related('employees')
        
        structure = {}
        for dept in departments:
            structure[dept] = {
                'employees': dept.employees.all(),
                'managers': dept.employees.filter(is_manager=True)
            }
            
        context['structure'] = structure
        return context 