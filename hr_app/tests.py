from django.test import TestCase, Client
from django.urls import reverse
from .models import User, Employee, Department, LeaveRequest

class HRAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.department = Department.objects.create(name="IT", description="IT Department")
        self.admin_user = User.objects.create_user(
            username="admin",
            password="admin123",
            role="admin"
        )
        self.employee = Employee.objects.create(
            user=self.admin_user,
            first_name="Test",
            last_name="Admin",
            email="admin@test.com",
            department=self.department
        )

    def test_login_required(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_employee_creation(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(reverse('employee-create'), {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@test.com',
            'department': self.department.id,
            'job_title': 'Developer'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(email='john@test.com').exists())

    def test_leave_request_workflow(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(reverse('leave-create'), {
            'employee': self.employee.id,
            'leave_type': 'vacation',
            'start_date': '2024-03-20',
            'end_date': '2024-03-25',
            'status': 'pending'
        })
        self.assertEqual(response.status_code, 302)
        leave = LeaveRequest.objects.first()
        self.assertEqual(leave.status, 'pending')

    def test_ip_tracking(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse('dashboard'), REMOTE_ADDR='192.168.1.1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session['is_at_workplace'])

class EmployeeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.department = Department.objects.create(name='IT')
        
    def test_employee_list_view(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('employee-list'))
        self.assertEqual(response.status_code, 200) 