from django import forms
from facture.models import Client
from datetime import datetime

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nomClient', 'emailClient', 'telephoneClient', 'sexClient', 'ageClient', 'adresseClient', 'villeClient']
        widgets = {
            'nomClient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom et prénom du client',
                'required': True
            }),
            'emailClient': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email du client',
                'required': True
            }),
            'telephoneClient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone du client'
            }),
            'sexClient': forms.Select(attrs={
                'class': 'form-control'
            }, choices=[
                ('', 'Choisir une option...'),
                ('Masculin', 'Masculin'),
                ('Féminin', 'Féminin'),
            ]),
            'ageClient': forms.Select(attrs={
                'class': 'form-control'
            }, choices=[
                ('', 'Choisir la tranche d\'âge...'),
                ('0-15', '0-15 ans'),
                ('15-25', '15-25 ans'),
                ('25-45', '25-45 ans'),
                ('45+', '45 ans et plus')
            ]),
            'adresseClient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse du client'
            }),
            'villeClient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville du client'
            })
        }
        
    def clean_email(self):
        email = self.cleaned_data.get('emailClient')
        if email and Client.objects.filter(email=email).exists():
            raise forms.ValidationError("Un client avec cet email existe déjà.")
        return email

