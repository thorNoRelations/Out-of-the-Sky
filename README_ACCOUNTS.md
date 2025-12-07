# Accounts App & User System Integration

This document details the new `accounts` app and the integration of the user system with the flight tracking features.

## 1. Overview
The `accounts` app manages user authentication (signup, login, logout) and the user's profile. It links the Django built-in `User` model to the `TrackedFlight` model (formerly `Flight` in the `home` app), allowing users to maintain a personal list of tracked flights.

## 2. Integration Instructions

### Step 1: Create the App
The `accounts` app has been created with the following structure:
- `models.py`: (Empty, as we modified `home/models.py`)
- `views.py`: Handles signup and profile display.
- `forms.py`: Custom `SignUpForm` with email support.
- `urls.py`: Defines routes for `/login/`, `/signup/`, `/profile/`.
- `templates/accounts/`: Contains `login.html`, `signup.html`, `profile.html`.

### Step 2: Modify Existing Models
The existing `Flight` model in `home/models.py` was renamed to `TrackedFlight` and updated to include a Foreign Key to the `User` model.

**Changes in `home/models.py`:**
```python
from django.contrib.auth.models import User

class TrackedFlight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracked_flights', null=True, blank=True)
    # ... existing fields ...
```

### Step 3: Update Settings
The `myproject/settings.py` file was updated to include:

```python
INSTALLED_APPS = [
    # ...
    'accounts',
]

# Redirects after login/logout
LOGIN_REDIRECT_URL = 'profile'
LOGOUT_REDIRECT_URL = 'home:index'
```

### Step 4: Update URLs
The `myproject/urls.py` file was updated to include the accounts URLs:

```python
path('accounts/', include('accounts.urls')),
```

### Step 5: Run Migrations
Migrations were created and applied to rename `Flight` to `TrackedFlight` and add the `user` field.

```bash
python manage.py makemigrations home
python manage.py migrate
```

## 3. Implementing Flight Tracking (Save Logic)

To fully enable the "Track Flight" feature where users can save flights to their profile, you need to implement a view that handles the "Track Flight" button click from the search results.

**Instructions:**

1.  **Create a URL and View:**
    In `home/urls.py` (or `search/urls.py`), add a path like `path('track/<str:flight_number>/', views.track_flight, name='track_flight')`.

2.  **Implement the View:**
    The view should ensure the user is logged in and then create a `TrackedFlight` instance linked to that user.

    ```python
    from django.contrib.auth.decorators import login_required
    from django.shortcuts import redirect
    from .models import TrackedFlight

    @login_required
    def track_flight(request, flight_number):
        # Fetch flight details (mock or API) based on flight_number
        # For demonstration, we create a basic record
        
        # Check if already tracked
        if not TrackedFlight.objects.filter(user=request.user, flight_number=flight_number).exists():
            TrackedFlight.objects.create(
                user=request.user,
                flight_number=flight_number,
                departing_city="Unknown", # You would fetch this
                arriving_city="Unknown",  # You would fetch this
                scheduled_departure=timezone.now(), # Placeholder
                scheduled_arrival=timezone.now()    # Placeholder
            )
        
        return redirect('profile')
    ```

3.  **Update the Template:**
    In `search/templates/search/search.html`, update the "Track Flight" button to wrap it in a form or link to this new URL.

    ```html
    <!-- Example using a form for POST request (Recommended) -->
    <form action="{% url 'home:track_flight' flight.flight_number %}" method="post">
        {% csrf_token %}
        <button type="submit" class="btn btn-small btn-primary">Track Flight</button>
    </form>
    ```

    *Note: If the user is not logged in, the `@login_required` decorator will redirect them to the login page (and then back to the tracking action if `next` parameter is handled, or to the profile).*

## 4. Verification
- **Sign Up:** Go to `/accounts/signup/` to create a new user.
- **Log In:** Go to `/accounts/login/` (or click "Log In" in navbar).
- **Profile:** After login, you are redirected to `/accounts/profile/`, showing your tracked flights.
- **Dashboard:** The main dashboard at `/flight/1/` (if flight ID 1 exists) still works but shows generic info. The personalized list is on the Profile page.
