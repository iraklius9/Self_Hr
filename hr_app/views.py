from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View, FormView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Avg
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
import math
import requests
import ipaddress
import csv
from django.core.mail import send_mail
import random
import string
from django.contrib.auth import login, logout, get_user_model
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.db.models import Sum, F
from django.db.models.functions import TruncDate

from .models import (
    Employee, Department, TimeEntry, LeaveRequest, 
    News, Notification, Role, LocationLog, TimeLog,
    PerformanceReview, PerformanceGoal
)
from .forms import (
    EmployeeForm, EmployeeUpdateForm, DepartmentForm, TimeEntryForm,
    LeaveRequestForm, LeaveRequestUpdateForm, NewsForm, RoleForm,
    EmployeeSearchForm, CustomAuthenticationForm,
    UserSignupForm, PerformanceReviewForm, SignupForm
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
        # Remove password reset URL from context
        if 'password_reset_url' in context:
            del context['password_reset_url']
        return context

    def dispatch(self, request, *args, **kwargs):
        if self.redirect_authenticated_user and self.request.user.is_authenticated:
            redirect_to = self.get_success_url()
            if redirect_to == self.request.path:
                raise ValueError(
                    "Redirection loop for authenticated user detected. Check that "
                    "your LOGIN_REDIRECT_URL doesn't point to a login page."
                )
            return HttpResponseRedirect(redirect_to)
        return super().dispatch(request, *args, **kwargs)

class CustomLogoutView(LogoutView):
    next_page = 'login'
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Clear any existing sessions
        request.session.flush()
        # Clear any existing cookies
        response.delete_cookie('sessionid')
        messages.success(request, _("წარმატებით გამოხვედით სისტემიდან!"))
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
        return hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(department__name__icontains=search_query)
            )
        return queryset.order_by('first_name', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EmployeeSearchForm(self.request.GET)
        context['page_obj'] = context['employees']
        return context

class EmployeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Employee
    template_name = 'hr_app/employee/detail.html'
    
    def test_func(self):
        employee = self.get_object()
        return (hasattr(self.request.user, 'role') and 
                self.request.user.role.role in ['admin', 'hr_manager']) or \
               self.request.user == employee.user

class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr_app/employee/create.html'
    success_url = reverse_lazy('employee-list')
    
    def form_valid(self, form):
        employee = form.save(commit=False)
        
        # Create a User for this Employee
        password = self.request.POST.get('password')
        if not password:
            password = 'default_password'  # Set a default if no password provided
            
        # Generate username from email
        username = employee.email.split('@')[0]
        base_username = username
        counter = 1
        
        # Ensure username is unique
        User = get_user_model()
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        # Check if a user with this email already exists
        try:
            # Use filter and first() instead of get() to avoid MultipleObjectsReturned
            existing_user = User.objects.filter(email=employee.email).first()
            
            if existing_user:
                # If user exists, use it instead of creating a new one
                user = existing_user
                # Update user info in case it changed
                user.first_name = employee.first_name
                user.last_name = employee.last_name
                # Only update password if it was provided
                if password != 'default_password':
                    user.set_password(password)
                user.save()
            else:
                # No existing user found, create a new one
                user = User.objects.create_user(
                    username=username,
                    email=employee.email,
                    password=password,
                    first_name=employee.first_name,
                    last_name=employee.last_name
                )
            
            # Create default role only if the user doesn't already have one
            if not hasattr(user, 'role') or not user.role:
                Role.objects.create(
                    user=user,
                    role='employee'
                )
            
            # Associate user with employee
            employee.user = user
            
            # Save the employee
            employee.save()
            
        except Exception as e:
            # Log the error and show a message
            print(f"Error creating user: {str(e)}")
            messages.error(self.request, _("შეცდომა მომხმარებლის შექმნისას: {str(e)}"))
            return self.form_invalid(form)
        
        messages.success(self.request, _("თანამშრომელი წარმატებით დაემატა"))
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
    template_name = 'hr_app/leave/list.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user role
        if hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']:
            # Admin sees all leave requests
            queryset = LeaveRequest.objects.all().select_related('employee')
        else:
            # Regular users see only their own leave requests
            try:
                employee = self.request.user.employee_profile
                queryset = LeaveRequest.objects.filter(employee=employee)
            except (Employee.DoesNotExist, AttributeError):
                queryset = LeaveRequest.objects.none()
        
        # Apply status filter if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Order by submission date, newest first
        return queryset.order_by('-submitted_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add employee to context for checking permissions
        try:
            context['employee'] = self.request.user.employee_profile
        except (Employee.DoesNotExist, AttributeError):
            context['employee'] = None
        
        # Include active leaves count only for admin/HR managers
        if hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']:
            today = timezone.now().date()
            active_leaves = LeaveRequest.objects.filter(
                status='approved',
                start_date__lte=today,
                end_date__gte=today
            ).count()
            context['active_leaves'] = active_leaves
        
        return context

class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'hr_app/leave/form.html'
    success_url = reverse_lazy('leave-request-list')

    def form_valid(self, form):
        form.instance.employee = self.request.user.employee_profile
        messages.success(self.request, _("შვებულების მოთხოვნა წარმატებით გაიგზავნა"))
        return super().form_valid(form)

class LeaveRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def post(self, request, pk):
        leave_request = get_object_or_404(LeaveRequest, pk=pk)
        action = request.POST.get('action')
        
        if action == 'approve':
            leave_request.status = 'approved'
            message = _("შვებულების მოთხოვნა დამტკიცებულია")
        elif action == 'reject':
            leave_request.status = 'rejected'
            message = _("შვებულების მოთხოვნა უარყოფილია")
        
        leave_request.save()
        
        # Create notification for employee
        Notification.objects.create(
            user=leave_request.employee.user,
            message=message
        )
        
        messages.success(request, message)
        return redirect('leave-request-list')

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

class NewsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = News
    form_class = NewsForm
    template_name = 'hr_app/news/form.html'
    success_url = reverse_lazy('news-list')

    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def form_valid(self, form):
        messages.success(self.request, _("სიახლე წარმატებით განახლდა"))
        return super().form_valid(form)

class NewsDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = News
    template_name = 'hr_app/news/delete.html'
    success_url = reverse_lazy('news-list')

    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("სიახლე წარმატებით წაიშალა"))
        return super().delete(request, *args, **kwargs)

# Notification Views
@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read = True
    notification.save()
    return JsonResponse({'status': 'success'})

# Department Views
class DepartmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Department
    template_name = 'hr_app/department/list.html'
    context_object_name = 'departments'
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

class DepartmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Department
    template_name = 'hr_app/department/form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('department-list')
    
    def test_func(self):
        return self.request.user.role.role == 'admin'

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
        
        try:
            employee = self.request.user.employee_profile
            context['employee'] = employee
            
            # Get recent time logs for the current user
            recent_time_logs = TimeEntry.objects.filter(
                employee=employee
            ).order_by('-check_in')[:5]
            context['recent_time_logs'] = recent_time_logs
            
            # Get pending leave requests
            if hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']:
                leave_requests = LeaveRequest.objects.filter(
                    status='pending'
                ).select_related('employee').order_by('-submitted_at')[:5]
                
                # Only calculate active leaves for admin/hr_manager
                today = timezone.now().date()
                active_leaves = LeaveRequest.objects.filter(
                    status='approved',
                    start_date__lte=today,
                    end_date__gte=today
                ).count()
                context['active_leaves'] = active_leaves
            else:
                leave_requests = LeaveRequest.objects.filter(
                    employee=employee,
                    status='pending'
                ).order_by('-submitted_at')[:5]
            
            context['leave_requests'] = leave_requests
            
            # Get recent news
            context['news'] = News.objects.all().order_by('-posted_at')[:3]
            
            # Get unread notifications
            context['notifications'] = Notification.objects.filter(
                user=self.request.user,
                read=False
            )[:5]
            
            # Get total employees count (for admin/hr_manager)
            if hasattr(self.request.user, 'role') and self.request.user.role.role in ['admin', 'hr_manager']:
                context['total_employees'] = Employee.objects.count()
            
        except (Employee.DoesNotExist, AttributeError):
            context['employee'] = None
            messages.warning(
                self.request, 
                _("თქვენ არ გაქვთ თანამშრომლის პროფილი. დაუკავშირდით ადმინისტრატორს.")
            )
        
        return context

@login_required
def check_notifications(request):
    """
    AJAX endpoint to check for new notifications
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
        
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

class SignupView(TemplateView):
    template_name = 'hr_app/auth/signup_disabled.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

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

class TimeTrackingView(LoginRequiredMixin, ListView):
    model = TimeEntry
    template_name = 'hr_app/time_tracking/list.html'
    context_object_name = 'time_entries'
    paginate_by = 10

    def get_queryset(self):
        queryset = TimeEntry.objects.all().select_related('employee')
        view_type = self.request.GET.get('view', 'daily')  # default to daily view
        today = timezone.now().date()
        
        if self.request.user.role.role in ['admin', 'hr_manager']:
            # Admin/HR manager view with search
            search_query = self.request.GET.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(employee__first_name__icontains=search_query) |
                    Q(employee__last_name__icontains=search_query)
                )
        else:
            # Regular employee view
            queryset = queryset.filter(employee=self.request.user.employee_profile)

        # Filter based on view type
        if view_type == 'daily':
            queryset = queryset.filter(check_in__date=today)
        elif view_type == 'weekly':
            week_start = today - timedelta(days=today.weekday())
            queryset = queryset.filter(check_in__date__gte=week_start)
        elif view_type == 'monthly':
            queryset = queryset.filter(
                check_in__year=today.year,
                check_in__month=today.month
            )
        
        return queryset.order_by('-check_in')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        view_type = self.request.GET.get('view', 'daily')
        context['current_view'] = view_type
        
        if self.request.user.role.role in ['admin', 'hr_manager']:
            # Admin view context
            search_query = self.request.GET.get('search')
            pending_entries = TimeEntry.objects.filter(check_out__isnull=True)
            
            if search_query:
                pending_entries = pending_entries.filter(
                    Q(employee__first_name__icontains=search_query) |
                    Q(employee__last_name__icontains=search_query)
                )
            
            context['pending_entries'] = pending_entries.select_related('employee')
        else:
            # Employee view context
            employee = self.request.user.employee_profile
            current_date = timezone.now()
            
            # Calculate totals based on view type
            if view_type == 'daily':
                entries = TimeEntry.objects.filter(
                    employee=employee,
                    check_in__date=current_date.date(),
                    check_out__isnull=False
                )
                context['period_label'] = _("დღის ჯამი")
            elif view_type == 'weekly':
                week_start = current_date.date() - timedelta(days=current_date.weekday())
                entries = TimeEntry.objects.filter(
                    employee=employee,
                    check_in__date__gte=week_start,
                    check_out__isnull=False
                )
                context['period_label'] = _("კვირის ჯამი")
            else:  # monthly
                entries = TimeEntry.objects.filter(
                    employee=employee,
                    check_in__year=current_date.year,
                    check_in__month=current_date.month,
                    check_out__isnull=False
                )
                context['period_label'] = _("თვის ჯამი")

            total_hours = sum(
                (entry.check_out - entry.check_in).total_seconds() / 3600 
                for entry in entries if entry.check_out
            )
            
            context.update({
                'period_total': round(total_hours, 2),
                'current_time_entry': TimeEntry.objects.filter(
                    employee=employee,
                    check_out__isnull=True
                ).first()
            })
        
        return context

class TimeTrackingCheckInView(LoginRequiredMixin, View):
    def post(self, request):
        employee = request.user.employee_profile

        # Check for active entry
        active_entry = TimeEntry.objects.filter(
            employee=employee,
            check_out__isnull=True
        ).first()

        if active_entry:
            messages.error(
                request, 
                _("თქვენ უკვე დაწყებული გაქვთ სამუშაო დრო %(time)s-ზე") % {
                    'time': active_entry.check_in.strftime('%H:%M')
                }
            )
            return redirect('time-tracking')

        # Create new time entry
        try:
            TimeEntry.objects.create(
                employee=employee,
                ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0')
            )
            messages.success(request, _("სამუშაო დრო დაიწყო"))
        except Exception as e:
            messages.error(request, _("შეცდომა სამუშაო დროის დაწყებისას. გთხოვთ სცადოთ თავიდან."))
            
        return redirect('time-tracking')

class TimeTrackingCheckOutView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            # Check if admin is closing someone else's entry
            entry_id = request.POST.get('entry_id')
            if entry_id and request.user.role.role in ['admin', 'hr_manager']:
                current_entry = TimeEntry.objects.get(id=entry_id)
            else:
                current_entry = TimeEntry.objects.filter(
                    employee=request.user.employee_profile,
                    check_out__isnull=True
                ).first()

            if not current_entry:
                messages.error(request, _("აქტიური სესია ვერ მოიძებნა"))
                return redirect('time-tracking')

            current_entry.check_out = timezone.now()
            current_entry.save()
            
            duration = current_entry.check_out - current_entry.check_in
            hours = duration.total_seconds() / 3600
            
            if request.user.role.role in ['admin', 'hr_manager']:
                messages.success(
                    request, 
                    _("%(employee)s-ის სამუშაო დრო დასრულდა. ნამუშევარი დრო: %(hours).2f საათი") % {
                        'employee': current_entry.employee.get_full_name(),
                        'hours': hours
                    }
                )
            else:
                messages.success(
                    request, 
                    _("სამუშაო დრო დასრულდა. იმუშავეთ %(hours).2f საათი") % {'hours': hours}
                )
        except Exception as e:
            messages.error(request, _("შეცდომა სამუშაო დროის დასრულებისას. გთხოვთ სცადოთ თავიდან."))
        
        return redirect('time-tracking')

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

class ReportsAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'hr_app/reports/dashboard.html'
    
    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        # Employee statistics
        context['total_employees'] = Employee.objects.count()
        context['employees_by_department'] = Department.objects.annotate(
            employee_count=Count('employees')
        )
        
        # Time tracking statistics
        context['time_entries'] = TimeEntry.objects.filter(
            check_in__date__gte=start_of_month
        ).values('employee__first_name', 'employee__last_name').annotate(
            total_hours=Sum('duration_hours'),
            avg_hours=Avg('duration_hours'),
            days_worked=Count('check_in__date', distinct=True)
        )
        
        # Leave statistics
        context['leave_requests'] = LeaveRequest.objects.filter(
            submitted_at__date__gte=start_of_month
        ).values('status').annotate(count=Count('id'))
        
        # Department statistics
        context['departments'] = Department.objects.annotate(
            employee_count=Count('employees'),
            avg_vacation_days=Avg('employees__vacation_days_left')
        )
        
        return context 

class PerformanceReviewListView(LoginRequiredMixin, ListView):
    model = PerformanceReview
    template_name = 'hr_app/performance/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.role.role in ['admin', 'hr_manager']:
            return PerformanceReview.objects.all().order_by('-review_date')
        return PerformanceReview.objects.filter(
            employee=self.request.user.employee_profile
        ).order_by('-review_date')

class PerformanceReviewCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = PerformanceReview
    template_name = 'hr_app/performance/review_form.html'
    form_class = PerformanceReviewForm
    success_url = reverse_lazy('performance-review-list')

    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def form_valid(self, form):
        form.instance.reviewer = self.request.user.employee_profile
        messages.success(self.request, _("შეფასება წარმატებით დაემატა"))
        return super().form_valid(form)

class PerformanceReviewDetailView(LoginRequiredMixin, DetailView):
    model = PerformanceReview
    template_name = 'hr_app/performance/review_detail.html'
    context_object_name = 'review'

    def get_queryset(self):
        if self.request.user.role.role in ['admin', 'hr_manager']:
            return PerformanceReview.objects.all()
        return PerformanceReview.objects.filter(employee=self.request.user.employee_profile)

class PerformanceReviewUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = PerformanceReview
    template_name = 'hr_app/performance/review_form.html'
    form_class = PerformanceReviewForm
    success_url = reverse_lazy('performance-review-list')

    def test_func(self):
        return self.request.user.role.role in ['admin', 'hr_manager']

    def form_valid(self, form):
        messages.success(self.request, _("შეფასება წარმატებით განახლდა"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        return context 