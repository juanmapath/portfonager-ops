from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # project apps
    path('api/botops/', include('apps.botops.urls')),
    path('api/proftview/', include('apps.proftview.urls')),
    # django admin
    path('admin/', admin.site.urls),
]