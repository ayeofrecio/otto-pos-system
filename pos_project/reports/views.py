from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def home(request):
    return HttpResponse("<h1>Welcome to the Report Page</h1> <p>This is where you can find all the latest posts and updates.</p>")
