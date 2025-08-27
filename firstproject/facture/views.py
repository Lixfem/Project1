from django.shortcuts import HttpResponse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from facture.forms import ClientForm
from django.core.mail import send_mail
from django.shortcuts import redirect 
from django.views import View
from .models import *
from django.contrib import messages

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
        return redirect('liste-client')
    
    return render(request,
                  'facture/client_delete.html')

