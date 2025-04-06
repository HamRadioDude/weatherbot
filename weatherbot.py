import os
import time
import json
import requests
import datetime
import socket
from meshtastic.tcp_interface import TCPInterface

# --- Configuration ---
DATA_PATH = "data"
SETTINGS_FILE = os.path.join(DATA_PATH, "settings.json")
ALERTS_FILE = os.path.join(DATA_PATH, "alerts.json")
MAX_MSG_LEN = 180

# --- Emoji map for weather descriptions ---
WEATHER_EMOJIS = {
    "clear sky": "☀️",
    "few clouds": "🌤️",
    "scattered clouds": "🌥️",
    "broken clouds": "☁️",
    "overcast clouds": "☁️",
    "light rain": "🌦️",
    "moderate rain": "🌧️",
    "heavy intensity rain": "🌧️",
    "thunderstorm": "⛈️",
    "snow": "❄️",
    "mist": "🌫️",
    "fog": "🌫️",
    "haze": "🌫️",
    "drizzle": "🌦️"
}

# --- Load settings ---
def load_settings():
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

# --- Check for internet ---
def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# --- Split messages ---
def split_message(text):
    words = text.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= MAX_MSG_LEN:
            current += (word + " ")
        else:
            chunks.append(current.strip())
            current = word + " "
    if current:
        chunks.append(current.strip())

    return [f"({i+1}/{len(chunks)}) {chunk}" for i, chunk in enumerate(chunks)]

# --- TCP interface wrapper ---
def get_interface():
    try:
        return TCPInterface("127.0.0.1")
    except Exception as e:
        print(f"[WeatherBot] Error initializing TCPInterface: {e}")
        return None

# --- Send message ---
def send_to_meshtastic(chunks, channel_index):
    global interface
    for chunk in chunks:
        try:
            interface.sendText(chunk, channelIndex=channel_index)
            time.sleep(1)
        except BrokenPipeError:
            print("[WeatherBot] Broken pipe. Reinitializing TCPInterface...")
            interface = get_interface()

# --- Weather API helpers ---
def get_weather_data(endpoint, params):
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API error: {e}")
        return None

def get_lat_lon(settings):
    endpoint = "https://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": settings["location"],
        "limit": 1,
        "appid": settings["api_key"]
    }
    data = get_weather_data(endpoint, params)
    if data and len(data) > 0:
        return data[0]["lat"], data[0]["lon"]
    return None, None

def weather_with_emoji(description):
    return f"{WEATHER_EMOJIS.get(description.lower(), '')} {description}"

def get_current_weather(settings):
    endpoint = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": settings["location"],
        "appid": settings["api_key"],
        "units": "imperial"
    }
    data = get_weather_data(endpoint, params)
    if data:
        desc = data['weather'][0]['description']
        emoji_desc = weather_with_emoji(desc)
        return f"Current weather in {data['name']}: {emoji_desc}, {data['main']['temp']}°F"

def get_hourly_forecast(settings):
    lat, lon = get_lat_lon(settings)
    if not lat or not lon:
        return None
    endpoint = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings["api_key"],
        "units": "imperial",
        "exclude": "minutely,daily,alerts,current"
    }
    data = get_weather_data(endpoint, params)
    if data and "hourly" in data:
        out = "Next 5 hours:\n"
        for hour in data["hourly"][:5]:
            dt = datetime.datetime.fromtimestamp(hour["dt"]).strftime('%I %p')
            temp = hour["temp"]
            desc = hour["weather"][0]["description"]
            emoji_desc = weather_with_emoji(desc)
            out += f"\n{dt}: {emoji_desc}, {temp}°F"
        return out.strip()

def get_daily_forecast(settings):
    lat, lon = get_lat_lon(settings)
    if not lat or not lon:
        return None
    endpoint = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings["api_key"],
        "units": "imperial",
        "exclude": "minutely,hourly,alerts,current"
    }
    data = get_weather_data(endpoint, params)
    if data and "daily" in data:
        out = "5-day forecast:\n"
        for day in data["daily"][:5]:
            dt = datetime.datetime.fromtimestamp(day["dt"]).strftime('%a')
            desc = day["weather"][0]["description"]
            temp = day["temp"]["day"]
            emoji_desc = weather_with_emoji(desc)
            out += f"\n{dt}: {emoji_desc}, {temp}°F"
        return out.strip()

# --- Alert tracking ---
def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return {}
    with open(ALERTS_FILE, 'r') as f:
        return json.load(f)

def save_alerts(alerts):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f)

def alert_not_seen(alert_id, stored_alerts):
    return alert_id not in stored_alerts

# --- Main loop ---
def main():
    global interface
    settings = load_settings()
    alerts_seen = load_alerts()
    channel_index = settings.get("channel_index", 0)
    interface = get_interface()

    last_weather_check = 0
    last_alert_check = 0
    weather_interval = 10 * 60
    alert_interval = 10 * 60
    active_alert_type = None

    while True:
        now = datetime.datetime.now()
        current_time = time.time()
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Checking schedule...")

        if not check_internet():
            print("[WeatherBot] ⚠️ No internet connection.")
            send_to_meshtastic(split_message("[WeatherBot] ⚠️ No connection. Skipping update."), channel_index)
            time.sleep(60)
            continue

        if current_time - last_weather_check >= weather_interval:
            print("[WeatherBot] Sending current weather update...")
            msg = get_current_weather(settings)
            if msg:
                send_to_meshtastic(split_message(msg), channel_index)

            print("[WeatherBot] Sending hourly forecast...")
            forecast = get_hourly_forecast(settings)
            if forecast:
                send_to_meshtastic(split_message(forecast), channel_index)

            print("[WeatherBot] Sending 5-day forecast...")
            forecast = get_daily_forecast(settings)
            if forecast:
                send_to_meshtastic(split_message(forecast), channel_index)

            last_weather_check = current_time

        if current_time - last_alert_check >= alert_interval:
            print("[WeatherBot] Checking for alerts...")
            # NOTE: Add real-time alert logic here if available from API version
            last_alert_check = current_time

        time.sleep(60)

if __name__ == "__main__":
    main()
