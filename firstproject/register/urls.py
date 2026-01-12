# register/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views as v   # ou le nom que tu veux

app_name = 'register'   # optionnel mais très utile pour les reverse()

urlpatterns = [
    path('register/',v.register, name='register'),
    #path('',include('firstproject.urls')),
    #path('',include('django.contrib.auth.urls')),
    #path('mailfinder/',v.email_finder, name= 'email_finder'),
    # path('password_reset_confirm/',auth_views.PasswordChangeView.as_view(
    #     template_name="registration/password_reset_confirm.html"
    # ), name='password_reset_confirm'),
    path('login/',v.LoginView.as_view(), name='login'),
    path('logout/',v.logout_view, name='logout'),
   # path('profile/',v.profile,name='profile'),
   # accounts/urls.py ou ton urls.py principal


    path('reset-password/', auth_views.PasswordResetView.as_view(
    template_name='registration/password_reset_form.html',
    email_template_name='registration/password_reset_email.html',
    subject_template_name='registration/password_reset_subject.txt',
    success_url=reverse_lazy('custom_password_reset_done')
), name='custom_password_reset'),

    path('reset-password/done/', auth_views.PasswordResetDoneView.as_view(
    template_name='registration/password_reset_done.html'
), name='custom_password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
    template_name='registration/password_reset_confirm.html',
    success_url=reverse_lazy('custom_password_reset_complete')
), name='custom_password_reset_confirm'),


    path('reset-password/complete/', auth_views.PasswordResetCompleteView.as_view(
    template_name='registration/password_reset_complete.html'
), name='custom_password_reset_complete'),

]