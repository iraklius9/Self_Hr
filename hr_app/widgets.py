from django.forms.widgets import DateInput, DateTimeInput

class CustomDateInput(DateInput):
    input_type = 'date'
    
    def __init__(self, attrs=None):
        default_attrs = {'class': 'form-control datepicker'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

class CustomDateTimeInput(DateTimeInput):
    input_type = 'datetime-local'
    
    def __init__(self, attrs=None):
        default_attrs = {'class': 'form-control datetimepicker'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs) 