"""
URL configuration for SmartGoAI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include

from myapp import views

urlpatterns = [
    path('signup/',views.signup),
    path('signup_post/',views.signup_post),
    path('login/',views.login_page),
    path('login_post/',views.login_post),
    path('home/',views.homepage),
    path('analyser/',views.Analyser),
    path('voice_to_text/',views.voice_to_text),
    path('plans/',views.plans),
    path('complete_task/',views.complete_task),
    path('history/',views.view_history),
    path('logout/',views.logout_post),
    path('complete_reminder/',views.complete_reminder),
  



]
