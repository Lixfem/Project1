from django.shortcuts import HttpResponse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from facture.forms import *
from django.core.mail import send_mail
from django.shortcuts import redirect 
from django.views import View
from .models import *
from django.contrib import messages
from django.db import transaction
from django.forms import formset_factory
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal
from datetime import datetime

class HomeView(View):
    template_name = 'facture/index.html'

    def get(self, request, *args, **kwargs):
        factures = Facturation.objects.select_related('clientFacture', 'factureSaveBy').all()
        devis = Devis.objects.select_related('clientDevis', 'devisSaveBys').all()
        context = {
            'factures': factures,
            'devis': devis
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        factures = Facturation.objects.select_related('clientFacture', 'factureSaveBy').all()
        devis = Devis.objects.select_related('clientDevis', 'devisSaveBys').all()
        context = {
            'factures': factures,
            'devis': devis
        }
        return render(request, self.template_name, context)


class addCustomerView(View):  # Utilisation de PascalCase pour le nom de la classe
    template_name = 'facture/ajouterClient.html'

    def get(self, request, *args, **kwargs):
        form = ClientForm()  # Créer un formulaire vide pour la requête GET
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)  # Ne pas sauvegarder directement dans la base
            client.clientSaveBy = request.user  # Associer l'utilisateur connecté
            client.save()  # Sauvegarder l'objet avec clientSaveBy défini
            messages.success(request, 'Client ajouté avec succès')
            return redirect('liste-clients')
        else :
            form = ClientForm()
        # Si le formulaire n'est pas valide, renvoyer le formulaire avec les erreurs
        return render(request, self.template_name, {'form': form})




class addFactureView(LoginRequiredMixin, View):
    template_name = 'facture/add_facture.html'

    def get_context(self):
        clients = Client.objects.select_related('clientSaveBy').all()
        return {'clients': clients}
    
    def generate_numero_facture(self):
        with transaction.atomic():
            last_facture = Facturation.objects.select_for_update().order_by('-id').first()
            if last_facture:
                try:
                    last_numero = int(last_facture.numeroFacture.split('-')[-1])
                    new_numero = last_numero + 1
                except (ValueError, IndexError):
                    new_numero = 1
            else:
                new_numero = 1
            return f"FACT-{datetime.now().year}-{new_numero:03d}"
    

    def get(self, request, *args, **kwargs):
        print('La méthode de requête est : ', request.method)
        print('Les données POST sont : ', request.POST)
        return render(request, self.template_name, self.get_context())
    
    #@transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            # Récupération des données de base
            client_id = request.POST.get('client')
            numero_facture = self.generate_numero_facture()
            total_general = request.POST.get('total_general')  # Correction du nom
            commentaire_facture = request.POST.get('commentaireFacture')
            
            # Validation des données obligatoires
            if not client_id or not numero_facture:
                messages.error(request, "Le client et le numéro de facture sont obligatoires.")
                return render(request, self.template_name, self.get_context())
            
            # Vérification de l'unicité du numéro de facture
            if Facturation.objects.filter(numeroFacture=numero_facture).exists():
                messages.error(request, f"Erreur : Le numéro de facture {numero_facture} existe déjà.")
                return render(request, self.template_name, self.get_context())
            
            # Récupération du client
            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                messages.error(request, "Client introuvable.")
                return render(request, self.template_name, self.get_context())
            
            # Création de la facture
            facture = Facturation.objects.create(
                numeroFacture=numero_facture,
                clientFacture=client,
                factureSaveBy=request.user,
                totalFacture=float(total_general) if total_general else 0.0,
                commentaireFacture=commentaire_facture or ''
            )
            
            # Traitement des produits
            produits_items = []
            i = 0
            while f'produits[{i}][nom]' in request.POST:
                nom = request.POST.get(f'produits[{i}][nom]')
                quantity = request.POST.get(f'produits[{i}][quantity]')
                unit_price = request.POST.get(f'produits[{i}][unit_price]')  # Correction du nom
                total_price = request.POST.get(f'produits[{i}][total_price]')  # Correction du nom
                
                if nom and quantity and unit_price:
                    produit = Produit(
                        factureProduit=facture,
                        nomProduit=nom,
                        quantity=int(quantity),
                        prixUnitaireProduit=float(unit_price),
                        total=float(total_price) if total_price else 0.0,
                        devisProduit= None
                    )
                    produits_items.append(produit)
                i += 1
            
            # Traitement des services
            services_items = []
            i = 0
            while f'services[{i}][nom]' in request.POST:
                nom = request.POST.get(f'services[{i}][nom]')
                montant = request.POST.get(f'services[{i}][montant]')  # Correction du nom
                
                if nom and montant:
                    service = Service(
                        factureService=facture,
                        nomService=nom,
                        montantDuService=float(montant),
                        devisService=None
                    )
                    services_items.append(service)
                i += 1
            
            # Sauvegarde en bulk
            if produits_items:
                Produit.objects.bulk_create(produits_items)
            
            if services_items:
                Service.objects.bulk_create(services_items)
            
            # Vérification que la facture contient au moins un produit ou service
            if not produits_items and not services_items:
                facture.delete()  # Supprimer la facture vide
                messages.error(request, "Une facture doit contenir au moins un produit ou un service.")
                return render(request, self.template_name, self.get_context())
            
            messages.success(request, f'Facture {numero_facture} créée avec succès !')
            return redirect('liste-facture')  # Redirection après succès
            
        except ValueError as e:
            messages.error(request, f"Erreur de format dans les données numériques : {str(e)}")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
        
        print('Les données POST sont : ', request.POST)

        return render(request, self.template_name, self.get_context())
    
    



def listClient(request):
    clients = Client.objects.all()
    return render(request,'facture/listClient.html',{"clients": clients})

def detailsClient(request,id):
    client = Client.objects.get(id=id)
    return render(request,
                  'facture/detailsClient.html',{'client':client})


def listfacture(request):
    factures = Facturation.objects.all()
    return render(request,
                  'facture/listeFacture.html', {'factures': factures})

def detailsFacture(request,id):
    facture = Facturation.objects.get(id=id)
    return render(request,
                  'facture/detailsFacture.html',{'facture':facture})

def addClient(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            send_mail(
                subject=f'Message from {form.cleaned_data["name"] or "anonyme"} via Facture Client form',
                message= form.cleaned_data['message'],
                from_email=form.cleaned_data['email'],
                recipient_list=['admin@facture.xyz'],

            )
        return redirect('email-sent')
    else:
        form = ClientForm()
    
    return render(request,
                  'facture/ajouterClient.html',
                  {'form':form})

def createClient(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()

            return redirect('details-clients',client.id)
    else:
        form = ClientForm()
    return render(request,
                  'facture/client_create.html',{'form':form})


def changeClient(request,id):
    client = Client.objects.get(id=id)
    if request.method=='POST':
        form = ClientForm(request.POST,instance=client)
        if form.is_valid:
            form.save()
            return redirect('details-clients',client.id)
    else:
        form = ClientForm(instance=client)
    return render(request,
                  'facture/client_update.html',{'form':form})


def deleteClient(request,id):
    client = Client.objects.get(id=id)
    if request.method=='POST':
        client.delete()
        return redirect('liste-clients')
    
    return render(request,
                  'facture/client_delete.html',{'client':client})

