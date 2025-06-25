from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime
import httpx
import urllib.parse

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

from datetime import datetime, timezone

def get_horaires(stop_id):
    params = {"MonitoringRef": stop_id}
    headers = {"apiKey": API_KEY}

    response = httpx.get(BASE_URL, params=params, headers=headers, timeout=10)
    data = response.json()
    visits = data["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0].get("MonitoredStopVisit", [])

    horaires = []
    nom_arret = "Inconnu"
    direction = "Inconnue"
    now = datetime.now(timezone.utc)

    for v in visits:
        call = v["MonitoredVehicleJourney"]["MonitoredCall"]
        arret = call["StopPointName"][0]["value"]
        direction_name = v["MonitoredVehicleJourney"]["DirectionName"][0]["value"]
        raw_time = call.get("ExpectedArrivalTime") or call.get("ExpectedDepartureTime")

        try:
            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if dt > now:  # ✅ ne garde que les horaires futurs
                horaires.append(dt.astimezone().strftime("%H:%M"))
                nom_arret = arret
                direction = direction_name
        except Exception:
            continue

        if len(horaires) >= 3:
            break

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
