from django.db import models
from django.contrib.auth.models import User


class USER(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10)
    age = models.IntegerField()
    place = models.CharField(max_length=100)
    photo = models.FileField(upload_to='profile_photos/')
    LOGIN=models.OneToOneField(User,on_delete=models.CASCADE)

class Plans(models.Model):
    USER = models.ForeignKey(USER,on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    description = models.TextField()
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=100, default='pending')
    destination = models.CharField(max_length=100, null=True, blank=True)
    event_type = models.CharField(max_length=100, null=True, blank=True)
    weather_condition = models.CharField(max_length=100, null=True, blank=True)
    temperature = models.CharField(max_length=50, null=True, blank=True)
    rain_expected = models.BooleanField(default=False)
    weather_advice = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    PLANS = models.ForeignKey(Plans,on_delete=models.CASCADE)
    task = models.CharField(max_length=300)
    completed = models.CharField(max_length=100, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class Reminder(models.Model):
    PLANS = models.ForeignKey(Plans,on_delete=models.CASCADE)
    message = models.CharField(max_length=300)
    reminder_time = models.DateTimeField()
    completed = models.CharField(max_length=100, default='pending')
    notified = models.BooleanField(default=False)

