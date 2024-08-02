from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class TimeStampedModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    middle_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="Mobile Number"
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}"

    def get_short_name(self):
        return self.email

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
