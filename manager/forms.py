from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class AdminUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    is_bot = forms.BooleanField(required=False)  # Custom field
    is_active = forms.BooleanField(required=False)  # ✅ Must declare manually too

    class Meta:
        model = User
        fields = ['username', 'email', 'is_active', 'is_bot', 'password1', 'password2']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super(AdminUserCreationForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
