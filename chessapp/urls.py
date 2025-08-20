from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manager/', include('manager.urls')),
    path('', include('account.urls')), 
    path('board/', include('chessgame.urls')), 
   # path('accounts/', include('django.contrib.auth.urls')),   For built in login/logout/password reset
]
