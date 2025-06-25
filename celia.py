from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import urllib.parse
from datetime import datetime, timezone

from datetime import datetime, timezone, timedelta
app = FastAPI()

API_KEY = "TTqTJV4QWutZHjiYDJNOrNc4d1YcN7aL"
BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring"

# Commandes autorisées
COMMANDES = {
    "maison:metro6": "STIF:StopPoint:Q:22179:",
    "maison:metro7": "STIF:StopPoint:Q:22365:",
    "maison:185": "STIF:StopPoint:Q:22920:",
    "maison:183": "STIF:StopPoint:Q:22920:",
    "maison:rerc": "STIF:StopPoint:Q:471988:",
    "maison:t6": "STIF:StopPoint:Q:478979:",
    "travail:rerc": "STIF:StopPoint:Q:22921:"
}

def format_time(time_str):
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M")
    except Exception:
        return None



def get_horaires(stop_id):
    params = {"MonitoringRef": stop_id}
    headers = {"apiKey": API_KEY}

    try:
        response = httpx.get(BASE_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return "Inconnu", "Inconnue", []

    visits = data.get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [{}])[0].get("MonitoredStopVisit", [])

    horaires = []
    nom_arret = "Inconnu"
    direction = "Inconnue"
    now_utc = datetime.now(timezone.utc)

    # Décalage horaire France (UTC+2 en été)
    france_tz = timezone(timedelta(hours=2))

    for v in visits:
        try:
            call = v["MonitoredVehicleJourney"]["MonitoredCall"]
            raw_time = call.get("ExpectedArrivalTime") or call.get("ExpectedDepartureTime")
            dt_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))

            if dt_utc > now_utc:
                horaires.append(dt_utc.astimezone(france_tz).strftime("%H:%M"))
                nom_arret = call["StopPointName"][0]["value"]
                direction = v["MonitoredVehicleJourney"]["DirectionName"][0]["value"]

            if len(horaires) >= 3:
                break
        except Exception:
            continue

    return nom_arret, direction, horaires



@app.post("/slack")
async def slack_command(request: Request):
    form = await request.form()
    text = form.get("text", "").strip()

    if text not in COMMANDES:
        return PlainTextResponse(f"Commande inconnue : {text}", status_code=200)

    stop_id = COMMANDES[text]
    try:
        arret, direction, horaires = get_horaires(stop_id)
        if not horaires:
            return PlainTextResponse(f"Aucun passage imminent à {arret}", status_code=200)
        
        horaires_str = ", ".join(horaires)
        return PlainTextResponse(
            f"Prochains passages à *{arret}* direction *{direction}* : {horaires_str}",
            status_code=200
        )
    except Exception as e:
        return PlainTextResponse(f"Erreur : {str(e)}", status_code=500)
