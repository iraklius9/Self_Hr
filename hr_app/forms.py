from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import Employee, Department, TimeEntry, LeaveRequest, News, Role, User, PerformanceReview
from django.core.exceptions import ValidationError
from django.utils import timezone
from .widgets import CustomDateInput, CustomDateTimeInput

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('ელ. ფოსტა'),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('შეიყვანეთ ელ. ფოსტა')})
    )
    password = forms.CharField(
        label=_('პაროლი'),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': _('შეიყვანეთ პაროლი')})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].help_text = None

    def clean(self):
        email = self.cleaned_data.get('username')  # Django still calls it username internally
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                # Find user by email
                user = User.objects.get(email=email)
                # Set username for Django's auth backend
                self.cleaned_data['username'] = user.username
                # Check if the password is valid
                if not user.check_password(password):
                    raise forms.ValidationError(_('არასწორი ელ. ფოსტა ან პაროლი'))
            except User.DoesNotExist:
                raise forms.ValidationError(_('არასწორი ელ. ფოსტა ან პაროლი'))

            # Set the user for the authentication backend
            self.user_cache = user

        return self.cleaned_data

class UserSignupForm(forms.ModelForm):
    first_name = forms.CharField(label=_("სახელი"), max_length=30)
    last_name = forms.CharField(label=_("გვარი"), max_length=30)
    email = forms.EmailField(label=_("ელ. ფოსტა"))
    password1 = forms.CharField(label=_("პაროლი"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("გაიმეორეთ პაროლი"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("ეს ელ. ფოსტა უკვე გამოყენებულია"))
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("პაროლები არ ემთხვევა"))
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        # Generate username from email (we'll still need it for Django's auth system)
        username = self.cleaned_data['email'].split('@')[0]
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{self.cleaned_data['email'].split('@')[0]}{counter}"
            counter += 1
            
        user.username = username
        user.set_password(self.cleaned_data["password1"])
        
        if commit:
            user.save()
        return user

class EmployeeForm(forms.ModelForm):
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'text',
            'placeholder': _('აირჩიეთ თარიღი')
        })
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'text',
            'placeholder': _('აირჩიეთ თარიღი')
        })
    )

    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'department', 'birth_date', 'start_date',
            'salary', 'gender'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.all()
        
        # Add labels
        self.fields['first_name'].label = _('სახელი')
        self.fields['last_name'].label = _('გვარი')
        self.fields['email'].label = _('ელ.ფოსტა')
        self.fields['phone'].label = _('ტელეფონი')
        self.fields['department'].label = _('დეპარტამენტი')
        self.fields['birth_date'].label = _('დაბადების თარიღი')
        self.fields['start_date'].label = _('დაწყების თარიღი')
        self.fields['salary'].label = _('საშუალო ხელფასი')
        self.fields['gender'].label = _('სქესი')

        # Add required field indicators
        for field_name in self.fields:
            if self.fields[field_name].required:
                self.fields[field_name].label = f"{self.fields[field_name].label} *"

class EmployeeUpdateForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ('phone',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ('name', 'description')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ['employee', 'check_in', 'check_out', 'ip_address']
        widgets = {
            'check_in': CustomDateTimeInput(),
            'check_out': CustomDateTimeInput(),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert datetime to format expected by datetime-local input
        if self.instance.check_in:
            self.initial['check_in'] = self.instance.check_in.strftime('%Y-%m-%dT%H:%M')
        if self.instance.check_out:
            self.initial['check_out'] = self.instance.check_out.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if check_in and check_out and check_in > check_out:
            raise ValidationError(_("შემოსვლის დრო ვერ იქნება გასვლის დროზე გვიან"))

        return cleaned_data

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': CustomDateInput(),
            'end_date': CustomDateInput(),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(_("დაწყების თარიღი ვერ იქნება დასრულების თარიღზე გვიან"))
            
            if start_date < timezone.now().date():
                raise ValidationError(_("წარსული თარიღით შვებულების მოთხოვნა შეუძლებელია"))

class LeaveRequestUpdateForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ('status',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'title': _('სათაური'),
            'content': _('შინაარსი'),
        }

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ('role',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class EmployeeSearchForm(forms.Form):
    search = forms.CharField(
        required=False, 
        label='',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('ძიება სახელით ან დეპარტამენტით')
        })
    )

class PerformanceReviewForm(forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = [
            'employee', 
            'review_period_start', 
            'review_period_end',
            'productivity_rating',
            'quality_rating',
            'initiative_rating',
            'teamwork_rating',
            'communication_rating',
            'comments',
            'goals'
        ]
        widgets = {
            'review_period_start': CustomDateInput(),
            'review_period_end': CustomDateInput(),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'goals': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add bootstrap classes to all fields
        for field in self.fields:
            if not isinstance(self.fields[field].widget, forms.Textarea):
                self.fields[field].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('review_period_start')
        end_date = cleaned_data.get('review_period_end')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError(_("შეფასების პერიოდის დაწყების თარიღი ვერ იქნება დასრულების თარიღზე გვიან"))
        
        return cleaned_data 

class SignupForm(forms.ModelForm):
    password1 = forms.CharField(label=_("პაროლი"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("გაიმეორეთ პაროლი"), widget=forms.PasswordInput)
    
    username = forms.CharField(
        label=_("მომხმარებლის სახელი"),
        max_length=150,
        help_text='',  # Remove the help text
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        help_texts = {
            'username': '',  # Remove help text for username
        }
        
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("პაროლები არ ემთხვევა"))
        return password2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user 