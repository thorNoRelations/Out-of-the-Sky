import os
from django.http import JsonResponse
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from datetime import timezone as _tz, datetime
from .models import ApiUsage
from .models import Flight
from backend.APICalls import OpenWeatherClient

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


def flight_detail(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    all_flights = Flight.objects.all()
    other_flights = all_flights.exclude(id=flight_id)[:5]

    on_time_count = all_flights.filter(estimated_departure__isnull=True).count()
    delayed_count = all_flights.exclude(estimated_departure__isnull=True).count()
    upcoming_count = all_flights.filter(scheduled_departure__gte=timezone.now()).count()

    context = {
        'flight': flight,
        'all_flights': all_flights,
        'other_flights': other_flights,
        'on_time_count': on_time_count,
        'delayed_count': delayed_count,
        'upcoming_count': upcoming_count,
    }
    return render(request, 'home/flight_detail.html', context)
# def weather_insights(request):
#     q = (request.GET.get("q") or request.GET.get("search") or "").strip()
#     status = {"query": q, "called_api": False, "error": None, "city": None, "temp": None}
#
#     weather = None
#     if q:
#         try:
#             client = OpenWeatherClient()
#             data = client.fetch_city(q)
#             status["called_api"] = True
#             status["city"] = data.get("name")
#             status["temp"] = (data.get("main") or {}).get("temp")
#             # minimal context your template can read
#             weather = {
#                 "city": status["city"],
#                 "temp": status["temp"],
#                 "country": (data.get("sys") or {}).get("country"),
#                 "condition": ((data.get("weather") or [{}])[0] or {}).get("description"),
#             }
#         except Exception as e:
#             status["error"] = str(e)
#
#     # show status at top of page so we see what's happening
#     return render(request, "home/weather_insights.html", {
#         "search_query": q,
#         "weather": weather,
#         "debug_status": status,
#     })
# def weather_insights(request):
#     q = (request.GET.get("q") or request.GET.get("search") or "").strip()
#     status = {"query": q, "called_api": False, "error": None, "city": None, "temp": None}
#
#     if q:
#         try:
#             client = OpenWeatherClient()
#             data = client.fetch_city(q)
#             status["called_api"] = True
#             status["city"] = data.get("name")
#             status["temp"] = (data.get("main") or {}).get("temp")
#         except Exception as e:
#             status["error"] = str(e)
#
#         # ⬅️ return JSON so we see exactly what's happening
#         return JsonResponse(status)
#
#     # No query: keep rendering the page
#     return render(request, "home/weather_insights.html", {"search_query": q})

# def weather_insights(request):
#     q = (request.GET.get("q") or request.GET.get("search") or "").strip()
#     weather, error = None, None
#
#     if q:
#         try:
#             data = OpenWeatherClient().fetch_city(q)
#             weather = {
#                 "city": data.get("name"),
#                 "country": (data.get("sys") or {}).get("country"),
#                 "temp": (data.get("main") or {}).get("temp"),
#                 "condition": ((data.get("weather") or [{}])[0] or {}).get("description"),
#             }
#         except Exception as e:
#             error = str(e)
#     debug_status = {"q": q, "has_weather": weather is not None, "error": error}
#
#     return render(request, "home/weather_insights.html", {
#         "search_query": q,
#         "weather": weather,
#         "error": error,
#         "debug_status": debug_status,
#     })
#

def weather_insights(request):
    q = (request.GET.get("q") or request.GET.get("search") or "").strip()
    weather = None         # keep if you also show the small banner at top
    airports_weather = []  # <-- template expects this list
    error = None

    if q:
        try:
            data = OpenWeatherClient().fetch_city(q)

            # small banner (optional)
            weather = {
                "city": data.get("name"),
                "country": (data.get("sys") or {}).get("country"),
                "temp": (data.get("main") or {}).get("temp"),
                "condition": ((data.get("weather") or [{}])[0] or {}).get("description"),
            }

            # build the list item the template loops over
            w = data.get("weather") or [{}]
            desc = (w[0] or {}).get("description", "")
            airports_weather = [{
                "airport_code": q.upper(),                          # e.g. "DENVER,US"
                "airport_name": data.get("name"),                   # "Denver"
                "temperature": (data.get("main") or {}).get("temp"),
                "wind_speed": (data.get("wind") or {}).get("speed"),
                "visibility": data.get("visibility"),               # template prints "mi" – set units as you like
                "precipitation_chance": 0,                          # /weather often lacks POP; default 0
                "forecast_time": datetime.fromtimestamp(data.get("dt", 0)),
                "delay_risk": "low",                                # string used in class "risk-{{ weather.delay_risk }}"
                "delay_probability": 0,
                "estimated_delay_minutes": 0,
                "forecast_description": desc.title(),
                "last_updated": timezone.now(),

                # fields the template *calls* but are fine as plain strings
                "get_weather_icon": "🌤️",
                "get_condition_display": desc.title(),
                "get_delay_risk_display": "Low",
            }]

        except Exception as e:
            error = str(e)

    return render(request, "home/weather_insights.html", {
        "search_query": q,
        "weather": weather,                 # small banner at top (optional)
        "airports_weather": airports_weather,  # <-- critical
        "total_airports": len(airports_weather),
        "error": error,
    })

def _budgets_from_env():
    return {
        "openweathermap": int(os.getenv("BUDGET_OPENWEATHERMAP_PER_DAY", 900)),
        "aviationweather": int(os.getenv("BUDGET_AVIATIONWEATHER_PER_DAY", 2000)),
        "aviationstack": int(os.getenv("BUDGET_AVIATIONSTACK_PER_DAY", 1000)),
        "opensky": int(os.getenv("BUDGET_OPENSKY_PER_DAY", int(os.getenv("BUDGET_OPENSPY_PER_DAY", 380)))),
    }

@staff_member_required
def api_usage_readout(request):
    today = timezone.now().astimezone(_tz.utc).strftime("%Y%m%d")
    budgets = _budgets_from_env()
    rows = ApiUsage.objects.filter(yyyymmdd=today).values("provider").annotate(total=Sum("count"))
    used = {r["provider"]: r["total"] for r in rows}
    out = []
    for provider, budget in budgets.items():
        u = int(used.get(provider, 0))
        remaining = max(0, budget - u)
        pct = (u / budget * 100.0) if budget else None
        out.append({
            "provider": provider,
            "used_today": u,
            "budget_today": budget,
            "remaining_today": remaining,
            "used_pct": round(pct, 1) if pct is not None else None,
        })
    return JsonResponse({"date": today, "providers": out})
