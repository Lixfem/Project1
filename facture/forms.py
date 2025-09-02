from django import forms
from .models import Facturation, Produit, Service, Client
from django.contrib.auth.models import User 
from datetime import datetime
from decimal import Decimal

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



class FacturationForm(forms.ModelForm):
    class Meta:
        model = Facturation
        fields = ['clientFacture', 'factureSaveBy', 'totalFacture', 'paid', 'statutFacture', 'numeroFacture', 'commentaireFacture']
        widgets = {
            'clientFacture': forms.Select(),
            'factureSaveBy': forms.Select(),
            'totalFacture': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'statutFacture': forms.Select(choices=Facturation.STATUT_CHOICES_FACTURATION),
            'numeroFacture': forms.TextInput(attrs={'class': 'form-control'}),
            'commentaireFacture': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'clientFacture': 'Client',
            'factureSaveBy': 'Créé par',
            'totalFacture': 'Montant total',
            'paid': 'Payé',
            'statutFacture': 'Statut',
            'numeroFacture': 'Numéro de facture',
            'commentaireFacture': 'Commentaire'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clientFacture'].queryset = Client.objects.all()
        self.fields['factureSaveBy'].queryset = User.objects.all()
        self.fields['numeroFacture'].initial=self.generate_numero_facture()
        self.fields['dateCreationFacture'] = forms.DateTimeField(
            widget=forms.DateTimeInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
            required=False,
            disabled=True
        )
        self.fields['lastUpdateFacture'] = forms.DateTimeField(
            widget=forms.DateTimeInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
            required=False,
            disabled=True
        )
        if self.instance and self.instance.pk:
            self.fields['dateCreationFacture'].initial = self.instance.dateCreationFacture
            self.fields['lastUpdateFacture'].initial = self.instance.lastUpdateFacture


    def generate_numero_facture(self):
        prefix = "FACT"
        year = datetime.now().strftime("%Y")
        last_facture = Facturation.objects.filter(numeroFacture__startswith=f"{prefix}-{year}").order_by('-numeroFacture').first()
        
        if last_facture:
            last_number = int(last_facture.numeroFacture.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"{prefix}-{year}-{new_number:03d}"
    
    def clean_numeroFacture(self):
        numero = self.cleaned_data.get('numeroFacture')
        if Facturation.objects.filter(numeroFacture=numero).exclude(pk=self.instance.id).exists():
            raise forms.ValidationError("Ce numéro de facture existe déjà.")
        return self.generate_numero_facture()
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.numeroFacture:
            instance.numeroFacture = self.cleaned_data['numeroFacture']
        if commit:
            instance.save()
        return instance

    
   
    def clean_totalFacture(self):
        total = self.cleaned_data.get('totalFacture')
        if total < 0:
            raise forms.ValidationError("Le montant total ne peut pas être négatif.")
        return total
    
    
class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['nomProduit', 'descriptionProduit', 'quantity', 'prixUnitaireProduit', 'total']
        widgets = {
            'nomProduit': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '40'}),
            'descriptionProduit': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '400'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'prixUnitaireProduit': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'total': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre les champs facultatifs pour les formsets
        for field_name, field in self.fields.items():
            field.required = False
    
    def clean_quantity(self):
        """Convertir en entier pour éviter les problèmes de type"""
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None:
            return int(quantity)
        return quantity
    
    def clean_prixUnitaireProduit(self):
        """Convertir en Decimal pour éviter les problèmes de type"""
        prix = self.cleaned_data.get('prixUnitaireProduit')
        if prix is not None:
            return Decimal(str(prix))
        return prix
    
    def clean_total(self):
        """Convertir en Decimal pour éviter les problèmes de type"""
        total = self.cleaned_data.get('total')
        if total is not None:
            return Decimal(str(total))
        return total


class ServiceForm(forms.ModelForm):
    datePrestationService = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False
    )
    
    class Meta:
        model = Service
        fields = ['nomService', 'descriptionService', 'montantDuService']
        widgets = {
            'nomService': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '60'}),
            'descriptionService': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '400'}),
            'montantDuService': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre les champs facultatifs pour les formsets
        for field_name, field in self.fields.items():
            field.required = False
        
        if self.instance and self.instance.pk:
            self.fields['datePrestationService'].initial = self.instance.datePrestationService
    
    def clean_montantDuService(self):
        """Convertir en Decimal pour éviter les problèmes de type"""
        montant = self.cleaned_data.get('montantDuService')
        if montant is not None:
            return Decimal(str(montant))
        return montant