from django.shortcuts import render, get_object_or_404
import models

def index(request):
    """
    View function for the landing page.
    Renders the main index.html template.
    """
    context = {
        'project_name': 'TaskFlow Pro',
        'tagline': 'Streamline Your Workflow, Amplify Your Productivity',
    }
    return render(request, 'home/index.html', context)

#View display for flight display feature
def flight_details(request, flight_id)

#Grabs flight from database, returns error if entered flight does not exist
flight = get_object_or_404(Flight, id=flight_id)

#Passes flight to the template
context = {
        'flight': flight,
    }

#Runs the template with the flight data 
return render(request, 'home/flight_detail.html', context)