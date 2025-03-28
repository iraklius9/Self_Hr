from django.core.management.base import BaseCommand
from django.utils import timezone
from hr_app.models import User, Employee, Role

class Command(BaseCommand):
    help = 'Creates an admin user and sets up their profile'

    def handle(self, *args, **options):
        try:
            # Try to get admin user
            admin_user = User.objects.get(username='admin')
            self.stdout.write(self.style.SUCCESS('✓ ადმინისტრატორი უკვე არსებობს'))
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING('! ადმინისტრატორი არ არსებობს, იქმნება ახალი...'))
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@gmail.com',
                password='admin123'
            )
            self.stdout.write(self.style.SUCCESS('✓ ადმინისტრატორი შეიქმნა წარმატებით'))

        # Create or update Employee profile
        try:
            employee, created = Employee.objects.get_or_create(
                user=admin_user,
                defaults={
                    'first_name': 'სისტემის',
                    'last_name': 'ადმინისტრატორი',
                    'email': 'admin@gmail.com',
                    'job_title': 'HR ადმინისტრატორი',
                    'start_date': timezone.now().date(),
                    'phone': '',
                    'address': ''
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS('✓ თანამშრომლის პროფილი შეიქმნა'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ თანამშრომლის პროფილი უკვე არსებობს'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ შეცდომა თანამშრომლის პროფილის შექმნისას: {str(e)}'))
            return

        # Set admin role
        try:
            role = Role.objects.get(user=admin_user)
            role.role = 'admin'
            role.save()
            self.stdout.write(self.style.SUCCESS('✓ ადმინისტრატორის როლი მინიჭებულია'))
        except Role.DoesNotExist:
            self.stdout.write(self.style.ERROR('✗ როლი ვერ მოიძებნა'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ შეცდომა როლის მინიჭებისას: {str(e)}'))
            return

        self.stdout.write(self.style.SUCCESS('\n✓ ადმინისტრატორის მომხმარებელი წარმატებით დაკონფიგურდა'))
        self.stdout.write('\nმონაცემები შესასვლელად:')
        self.stdout.write('  ელ. ფოსტა: admin@gmail.com')
        self.stdout.write('  პაროლი: admin123') 