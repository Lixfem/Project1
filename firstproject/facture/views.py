from django.shortcuts import HttpResponse
from django.shortcuts import render
from facture.models import Client 
from facture.models import Facturation
from django.shortcuts import get_object_or_404
from facture.forms import ClientForm
from django.core.mail import send_mail
from django.shortcuts import redirect 



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

