from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

class UserRegisterForm(UserCreationForm):
   class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email', 'first_name','last_name')

    
    
    
class EmailFinderForm(forms.Form):
    email = forms.EmailField(
        label= "Adresse e-mail",
        max_length= 254,
        widget= forms.EmailInput(attrs={'placeholder':'Entrez votre e-mail '}),
        required=True)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError(" Cet email n'est pas associé à un utilisateur.")
        return email
        

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True, label="Nom d'utilisateur")
    password = forms.CharField(max_length=63,widget=forms.PasswordInput, required=True, label="Mot de passe")

    
    