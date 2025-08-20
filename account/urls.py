from django.urls import path
from .views import signup_view , home
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', home, name='home'),
    
    path('signup/', signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('wallet/', views.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/request/<str:req_type>/', views.wallet_request, name='wallet_request'),
    path('api/login/', views.login_api, name='api_login'),
    path('api/signup/', views.signup_api, name='signup_api'),
    path('api/home/', views.home_api, name='home_api'),
    path('secwallet/', views.secwallet_dashboard, name='secwallet_dashboard'),
    path('secwallet/request/<str:req_type>/', views.secwallet_request, name='secwallet_request'),
    path('referrals/', views.referral_dashboard, name='referral_dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('secwallet/transfer/', views.transfer_to_secwallet, name='transfer_to_secwallet'),
 #   path('wallet/manage/', views.manage_wallet_requests, name='manage_wallet_requests'),
    # Password reset
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='user/password_reset_form.html'), name='password_reset'),
    #path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    #path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    #path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

]
