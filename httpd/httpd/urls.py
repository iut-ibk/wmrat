from django.urls import path, include
from hub import views

urlpatterns = [
    path('', include('hub.urls')),
]
