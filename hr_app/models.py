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
    name = models.CharField(_("დასახელება"), max_length=100)
    description = models.TextField(_("აღწერა"), blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Employee(models.Model):
    GENDER_CHOICES = (
        ('male', _('მამრობითი')),
        ('female', _('მდედრობითი')),
        ('other', _('სხვა')),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile', null=True, blank=True)
    first_name = models.CharField(_('სახელი'), max_length=100)
    last_name = models.CharField(_('გვარი'), max_length=100)
    email = models.EmailField(_('ელ.ფოსტა'), unique=True)
    phone = models.CharField(_('ტელეფონი'), max_length=50, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, related_name='employees')
    birth_date = models.DateField(_('დაბადების თარიღი'), null=True, blank=True)
    start_date = models.DateField(_('დაწყების თარიღი'))
    salary = models.DecimalField(_('ხელფასი'), max_digits=10, decimal_places=2, default=0)
    gender = models.CharField(_('სქესი'), max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_employees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    vacation_days_left = models.PositiveIntegerField(_("დარჩენილი შვებულების დღეები"), default=20)
    profile_picture = models.ImageField(_("პროფილის სურათი"), upload_to='profile_pics/', null=True, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates',
                                verbose_name=_("მენეჯერი"))

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = _('თანამშრომელი')
        verbose_name_plural = _('თანამშრომლები')


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
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='time_entries')
    check_in = models.DateTimeField(_('შემოსვლის დრო'), default=timezone.now)
    check_out = models.DateTimeField(_('გასვლის დრო'), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_('IP მისამართი'))

    @property
    def duration_hours(self):
        """Calculate duration in decimal hours"""
        if self.check_out and self.check_in:
            duration = self.check_out - self.check_in
            return round(duration.total_seconds() / 3600, 2)
        return 0.0

    @classmethod
    def get_total_hours_for_day(cls, employee, date):
        """Calculate total hours worked for a specific day"""
        entries = cls.objects.filter(
            employee=employee,
            check_in__date=date,
            check_out__isnull=False
        )
        total_hours = sum(entry.duration_hours for entry in entries)
        return round(total_hours, 2)

    @classmethod
    def get_total_hours_for_month(cls, employee, year, month):
        """Calculate total hours worked for a specific month"""
        entries = cls.objects.filter(
            employee=employee,
            check_in__year=year,
            check_in__month=month,
            check_out__isnull=False
        )
        total_hours = sum(entry.duration_hours for entry in entries)
        return round(total_hours, 2)

    class Meta:
        ordering = ['-check_in']
        verbose_name = _('დროის ჩანაწერი')
        verbose_name_plural = _('დროის ჩანაწერები')

    def __str__(self):
        return f"{self.employee} - {self.check_in.strftime('%Y-%m-%d %H:%M')}"


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('vacation', _('შვებულება')),
        ('sick', _('ავადმყოფობა')),
        ('other', _('სხვა')),
    ]
    STATUS_CHOICES = [
        ('pending', _('განხილვის პროცესში')),
        ('approved', _('დამტკიცებული')),
        ('rejected', _('უარყოფილი')),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_leave_type_display()}"


class News(models.Model):
    title = models.CharField(_("სათაური"), max_length=200)
    content = models.TextField(_("შინაარსი"))
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    posted_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class LocationLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='location_logs',
                                 verbose_name=_("თანამშრომელი"))
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
                message=_("ახალი შვებულების მოთხოვნა: {} - {}").format(instance.employee,
                                                                       instance.get_leave_type_display())
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
        (1, _('არადამაკმაყოფილებელი')),
        (2, _('საჭიროებს გაუმჯობესებას')),
        (3, _('დამაკმაყოფილებელი')),
        (4, _('კარგი')),
        (5, _('შესანიშნავი'))
    ]

    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='performance_reviews')
    reviewer = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='reviews_given')
    review_date = models.DateField(auto_now_add=True)
    review_period_start = models.DateField()
    review_period_end = models.DateField()

    # Performance Metrics with default values
    productivity_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    quality_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    initiative_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    teamwork_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    communication_rating = models.IntegerField(choices=RATING_CHOICES, default=3)

    comments = models.TextField(blank=True)
    goals = models.TextField(blank=True)

    @property
    def average_rating(self):
        ratings = [
            self.productivity_rating,
            self.quality_rating,
            self.initiative_rating,
            self.teamwork_rating,
            self.communication_rating
        ]
        return sum(ratings) / len(ratings)


class PerformanceGoal(models.Model):
    STATUS_CHOICES = [
        ('pending', _('მიმდინარე')),
        ('completed', _('დასრულებული')),
        ('cancelled', _('გაუქმებული'))
    ]

    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='performance_goals')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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
