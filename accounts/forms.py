from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UserChangeForm,
)

from .models import User
from .utils import generate_random_string


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={"autofocus": True, "placeholder": "Enter your email"}
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
    )
    verification_token = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Enter the token below"}),
    )
