from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SignUpForm2(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']





class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    referral_code = forms.CharField(max_length=30, required=False, help_text="Enter referral code (optional)")

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2','referral_code']

    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
