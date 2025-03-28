from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import Employee, Department, TimeEntry, LeaveRequest, News, Role, User

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
    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'job_title', 'start_date']
        widgets = {
            'start_date': forms.DateInput(
                attrs={
                    'class': 'form-control datepicker',
                    'type': 'text',
                    'placeholder': _('აირჩიეთ თარიღი'),
                    'autocomplete': 'off'
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        # Make sure department field shows all departments
        self.fields['department'].queryset = Department.objects.all()

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
        fields = ('employee', 'date', 'hours_worked', 'overtime', 'notes')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        labels = {
            'leave_type': _('შვებულების ტიპი'),
            'start_date': _('დაწყების თარიღი'),
            'end_date': _('დასრულების თარიღი'),
            'reason': _('მიზეზი')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].widget = forms.DateInput(
            attrs={
                'class': 'form-control datepicker',
                'type': 'text',
                'placeholder': _('აირჩიეთ თარიღი'),
                'autocomplete': 'off'
            }
        )
        self.fields['end_date'].widget = forms.DateInput(
            attrs={
                'class': 'form-control datepicker',
                'type': 'text',
                'placeholder': _('აირჩიეთ თარიღი'),
                'autocomplete': 'off'
            }
        )
        self.fields['reason'].widget = forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('მიუთითეთ შვებულების მიზეზი')
            }
        )
        self.fields['leave_type'].widget.attrs.update({'class': 'form-control'})

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
        fields = ('title', 'content', 'image')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

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