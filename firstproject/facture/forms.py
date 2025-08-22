from django import forms
from facture.models import Client
from datetime import datetime

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        #fields = '__all__'
        exclude = ('clientSaveBy',)

