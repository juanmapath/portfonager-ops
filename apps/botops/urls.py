from django.urls import path
from .views import ExecuteBotsView

urlpatterns = [
    path('execute/', ExecuteBotsView.as_view(), name='execute-bots'),
]
