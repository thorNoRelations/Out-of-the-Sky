from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm
from home.models import TrackedFlight

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('profile')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def profile(request):
    # Requirement: "list of all TrackedFlight objects owned by the logged-in user"
    # Assuming TrackedFlight has a 'user' field as per instructions.
    flights = TrackedFlight.objects.filter(user=request.user)
    return render(request, 'accounts/profile.html', {'flights': flights})