from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import math

# Define User model first
class User(AbstractUser):
    @property
    def is_admin(self):
        return hasattr(self, 'role') and self.role.role == 'admin'
    
    @property
    def is_hr_manager(self):
        return hasattr(self, 'role') and self.role.role == 'hr_manager'
    
    @property
    def is_employee(self):
        return hasattr(self, 'role') and self.role.role == 'employee'

    class Meta:
        db_table = 'hr_app_user'
        swappable = 'AUTH_USER_MODEL'

class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    job_title = models.CharField(max_length=100)
    start_date = models.DateField()
    vacation_days_left = models.PositiveIntegerField(_("დარჩენილი შვებულების დღეები"), default=20)
    profile_picture = models.ImageField(_("პროფილის სურათი"), upload_to='profile_pics/', null=True, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates', verbose_name=_("მენეჯერი"))
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    class Meta:
        verbose_name = _("თანამშრომელი")
        verbose_name_plural = _("თანამშრომლები")

class Role(models.Model):
    ROLE_CHOICES = (
        ('admin', _('ადმინისტრატორი')),
        ('hr_manager', _('HR მენეჯერი')),
        ('employee', _('თანამშრომელი')),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role')
    role = models.CharField(_("როლი"), max_length=20, choices=ROLE_CHOICES, default='employee')
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    class Meta:
        verbose_name = _("როლი")
        verbose_name_plural = _("როლები")

class TimeEntry(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='time_entries')
    date = models.DateField(_("თარიღი"))
    hours_worked = models.DecimalField(_("ნამუშევარი საათები"), max_digits=4, decimal_places=2)
    overtime = models.DecimalField(_("ზეგანაკვეთური"), max_digits=4, decimal_places=2, default=0)
    notes = models.TextField(_("შენიშვნები"), blank=True)
    
    def __str__(self):
        return f"{self.employee} - {self.date} ({self.hours_worked} hrs)"
    
    class Meta:
        verbose_name = _("დროის ჩანაწერი")
        verbose_name_plural = _("დროის ჩანაწერები")
        ordering = ['-date']

class LeaveRequest(models.Model):
    LEAVE_TYPES = (
        ('annual', _('ყოველწლიური')),
        ('sick', _('ავადმყოფობის')),
        ('personal', _('პირადი')),
        ('other', _('სხვა')),
    )
    
    STATUS_CHOICES = (
        ('pending', _('განხილვის პროცესში')),
        ('approved', _('დამტკიცებული')),
        ('rejected', _('უარყოფილი')),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_leave_type_display()}"

class News(models.Model):
    title = models.CharField(_("სათაური"), max_length=200)
    content = models.TextField(_("შინაარსი"))
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("გამომქვეყნებელი"))
    posted_at = models.DateTimeField(_("გამოქვეყნების თარიღი"), auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = _("სიახლე")
        verbose_name_plural = _("სიახლეები")
        ordering = ['-posted_at']

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(_("შეტყობინება"), max_length=255)
    read = models.BooleanField(_("წაკითხული"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.message[:30]}"
    
    class Meta:
        ordering = ['-created_at']

class LocationLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='location_logs', verbose_name=_("თანამშრომელი"))
    ip_address = models.GenericIPAddressField(_("IP მისამართი"))
    latitude = models.FloatField(_("განედი"), null=True, blank=True)
    longitude = models.FloatField(_("გრძედი"), null=True, blank=True)
    timestamp = models.DateTimeField(_("დრო"), auto_now_add=True)
    is_at_workplace = models.BooleanField(_("სამუშაო ადგილზეა"), default=False)
    
    def __str__(self):
        return f"{self.employee} - {self.timestamp.strftime('%Y-%m-%d %H:%M')} - {'✓' if self.is_at_workplace else '✗'}"
    
    class Meta:
        verbose_name = _("ლოკაციის ჩანაწერი")
        verbose_name_plural = _("ლოკაციის ჩანაწერები")
        ordering = ['-timestamp']

@receiver(post_save, sender=LeaveRequest)
def leave_request_notification(sender, instance, created, **kwargs):
    if created:
        # Notify HR managers about new leave request
        hr_managers = User.objects.filter(role__role='hr_manager')
        for manager in hr_managers:
            Notification.objects.create(
                user=manager,
                message=_("ახალი შვებულების მოთხოვნა: {} - {}").format(instance.employee, instance.get_leave_type_display())
            )
    elif instance.status != 'pending':
        # Notify employee about status change
        Notification.objects.create(
            user=instance.employee.user,
            message=_("თქვენი შვებულების მოთხოვნის სტატუსი შეიცვალა: {}").format(instance.get_status_display())
        )

class OnboardingTask(models.Model):
    CATEGORY_CHOICES = [
        ('documents', 'დოკუმენტაცია'),
        ('training', 'ტრენინგი'),
        ('equipment', 'აღჭურვილობა'),
        ('access', 'წვდომა'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='onboarding_tasks')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    completed = models.BooleanField(default=False)
    due_date = models.DateField()
    
    def __str__(self):
        return f"{self.title} - {self.employee.get_full_name()}"

class PerformanceReview(models.Model):
    RATING_CHOICES = [
        (1, 'არადამაკმაყოფილებელი'),
        (2, 'საჭიროებს გაუმჯობესებას'),
        (3, 'დამაკმაყოფილებელი'),
        (4, 'კარგი'),
        (5, 'შესანიშნავი'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performance_reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE)
    review_date = models.DateField()
    performance_rating = models.IntegerField(choices=RATING_CHOICES)
    strengths = models.TextField()
    areas_for_improvement = models.TextField()
    goals = models.TextField()
    comments = models.TextField(blank=True)
    
    def __str__(self):
        return f"Review for {self.employee.get_full_name()} on {self.review_date}"

class Document(models.Model):
    DOCUMENT_TYPES = [
        ('contract', 'კონტრაქტი'),
        ('id', 'პირადობის მოწმობა'),
        ('cv', 'CV'),
        ('certificate', 'სერტიფიკატი'),
        ('other', 'სხვა'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.employee.get_full_name()}"

class TimeLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='time_logs')
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    
    class Meta:
        ordering = ['-check_in']
        verbose_name = _("დროის აღრიცხვა")
        verbose_name_plural = _("დროის აღრიცხვები")

    def __str__(self):
        return f"{self.employee} - {self.check_in.date() if self.check_in else 'No check-in'}"

    def get_duration(self):
        if self.check_in and self.check_out:
            duration = self.check_out - self.check_in
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours}:{minutes:02d}"
        return None

# Create a signal to automatically create a Role when a User is created
@receiver(post_save, sender=User)
def create_user_role(sender, instance, created, **kwargs):
    if created:
        Role.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_role(sender, instance, **kwargs):
    if not hasattr(instance, 'role'):
        Role.objects.create(user=instance)
    else:
        instance.role.save() 