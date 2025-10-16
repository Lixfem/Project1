from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .forms import UserRegisterForm, EmailFinderForm, LoginForm
from django.contrib import messages 
from django.conf import settings
from django.urls import reverse
#from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import update_session_auth_hash  # Pour mettre à jour la session si l'utilisateur est connecté
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.decorators import login_required
from django.views import View



def register(request): 
    if request.method == 'POST':
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(settings.LOGIN_REDIRECT_URL)  
    else:
        form = UserRegisterForm()
    return render(request, 'registration/register.html', {'form': form})



def email_finder(request):
    if request.method == 'POST':
        form = EmailFinderForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = get_object_or_404(User, email=email)
            
            # Stocker l'ID de l'utilisateur dans la session pour la vue suivante
            request.session['reset_user_id'] = user.id
            
            # Rediriger vers la page de changement de mot de passe (adaptez l'URL si nécessaire)
            return redirect('password_reset_confirm')  # Ou le nom de votre vue de reset
        else:
            messages.error(request, "Cet e-mail n'est pas associé à un compte.")
    else:
        form = EmailFinderForm()
    
    return render(request, 'registration/email_finder.html', {'form': form})


def password_reset_confirm(request):
    # Vérifier si l'ID utilisateur est dans la session
    reset_user_id = request.session.get('reset_user_id')
    if not reset_user_id:
        messages.error(request, "Session invalide. Veuillez recommencer.")
        return redirect('email_finder')
    
    user = get_object_or_404(User, id=reset_user_id)
    
    if request.method == 'POST':
        form = SetPasswordForm(user=user, data=request.POST)
        if form.is_valid():
            form.save()
            # Nettoyer la session pour la sécurité
            if 'reset_user_id' in request.session:
                del request.session['reset_user_id']
            # Mettre à jour la session si l'utilisateur est connecté (optionnel)
            if request.user.is_authenticated:
                update_session_auth_hash(request, user)
            messages.success(request, "Mot de passe changé avec succès. Veuillez vous connecter.")
            return redirect('login')  # Redirection explicite vers la page de login
        else:
            messages.error(request, "Erreur lors du changement de mot de passe.")
    else:
        form = SetPasswordForm(user=user)
    
    return render(request, 'registration/password_reset_confirm.html', {'form': form})

class LoginView(View):
    template_name = 'registration/login.html'
    form_class = LoginForm

    def get(self,request):
        form = self.form_class()
        return render(request, self.template_name, context={'form':form})

    def post(self,request):
        if request.method == 'POST':
            form = self.form_class(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password'] 
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect('home')
                else:
                    messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            form = self.form_class()
        
        return render(request, self.template_name, {'form': form, 'messages': messages})



def logout_view(request):
    logout(request)
    return redirect('login')




