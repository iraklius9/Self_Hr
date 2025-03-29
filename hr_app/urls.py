from django.urls import path
from . import views
from .views import SignupView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', login_required(views.DashboardView.as_view()), name='dashboard'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    
    # Employee URLs
    path('employees/', login_required(views.EmployeeListView.as_view()), name='employee-list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee-create'),
    path('employees/<int:pk>/', views.EmployeeDetailView.as_view(), name='employee-detail'),
    path('employees/<int:pk>/update/', views.EmployeeUpdateView.as_view(), name='employee-update'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='employee-delete'),
    
    # Leave URLs
    path('leave/', views.LeaveRequestListView.as_view(), name='leave-list'),
    path('leave/create/', views.LeaveRequestCreateView.as_view(), name='leave-create'),
    path('leave/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave-detail'),
    path('leave/<int:pk>/update/', views.LeaveRequestUpdateView.as_view(), name='leave-update'),
    
    # Time Entry URLs
    path('time/', views.TimeEntryListView.as_view(), name='time-list'),
    path('time/add/', views.TimeEntryCreateView.as_view(), name='time-create'),
    
    # News URLs
    path('news/', views.NewsListView.as_view(), name='news-list'),
    path('news/create/', views.NewsCreateView.as_view(), name='news-create'),
    path('news/<int:pk>/edit/', views.NewsUpdateView.as_view(), name='news-update'),
    path('news/<int:pk>/delete/', views.NewsDeleteView.as_view(), name='news-delete'),
    
    # Department URLs
    path('departments/', views.DepartmentListView.as_view(), name='department-list'),
    path('departments/add/', views.DepartmentCreateView.as_view(), name='department-create'),
    path('departments/<int:pk>/update/', views.DepartmentUpdateView.as_view(), name='department-update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department-delete'),
    
    # Notification URLs
    path('notifications/check/', views.check_notifications, name='check-notifications'),
    path('notifications/<int:pk>/mark-read/', views.mark_notification_read, name='mark-notification-read'),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('leave/<int:pk>/update-status/', views.LeaveRequestUpdateStatusView.as_view(), name='leave-update-status'),
    path('leave-requests/', views.LeaveRequestListView.as_view(), name='leave-request-list'),
    path('leave-requests/create/', views.LeaveRequestCreateView.as_view(), name='leave-request-create'),
    path('leave-requests/<int:pk>/update/', views.LeaveRequestUpdateStatusView.as_view(), name='leave-request-update'),
    path('leave-requests/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave-request-detail'),
    path('time-tracking/', views.TimeTrackingView.as_view(), name='time-tracking'),
    path('time-tracking/checkin/', views.TimeTrackingCheckInView.as_view(), name='time-tracking-checkin'),
    path('time-tracking/checkout/', views.TimeTrackingCheckOutView.as_view(), name='time-tracking-checkout'),
    path('organization/structure/', views.OrganizationalStructureView.as_view(), name='org-structure'),
    path('reports/', views.ReportsAnalyticsView.as_view(), name='reports-analytics'),
    path('performance/', views.PerformanceReviewListView.as_view(), name='performance-review-list'),
    path('performance/create/', views.PerformanceReviewCreateView.as_view(), name='performance-review-create'),
    path('performance/<int:pk>/', views.PerformanceReviewDetailView.as_view(), name='performance-review-detail'),
    path('performance/<int:pk>/update/', views.PerformanceReviewUpdateView.as_view(), name='performance-review-update'),
] 