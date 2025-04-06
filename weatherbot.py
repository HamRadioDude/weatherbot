import os
import time
import json
import requests
import datetime
import socket
from meshtastic.tcp_interface import TCPInterface

DATA_PATH = "data"
SETTINGS_FILE = os.path.join(DATA_PATH, "settings.json")
ALERTS_FILE = os.path.join(DATA_PATH, "alerts.json")
MAX_MSG_LEN = 180

WEATHER_CODES = {
    0: "☀️ Clear",
    1: "🌤️ Mostly clear",
    2: "🌥️ Partly cloudy",
    3: "☁️ Overcast",
    45: "🌫️ Fog",
    48: "🌫️ Rime fog",
    51: "🌦️ Light drizzle",
    53: "🌦️ Moderate drizzle",
    55: "🌦️ Dense drizzle",
    61: "🌧️ Light rain",
    63: "🌧️ Moderate rain",
    65: "🌧️ Heavy rain",
    66: "🌧️ Freezing rain",
    67: "🌧️ Heavy freezing rain",
    71: "❄️ Light snow",
    73: "❄️ Moderate snow",
    75: "❄️ Heavy snow",
    80: "🌧️ Light showers",
    81: "🌧️ Moderate showers",
    82: "🌧️ Violent showers",
    95: "⛈️ Thunderstorm",
    96: "⛈️ Thunderstorm with hail",
    99: "⛈️ Severe thunderstorm"
}

SEVERITY_INTERVALS = {
    "Extreme": 300,
    "Severe": 600,
    "Moderate": 1800,
    "Minor": 3600,
    "Unknown": 3600
}

def load_settings():
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

def load_sent_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_sent_alerts(alerts):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f)

def resolve_zip_to_latlon(zip_code, api_key):
    try:
        url = f"http://api.openweathermap.org/geo/1.0/zip?zip={zip_code},US&appid={api_key}"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return data["lat"], data["lon"]
    except Exception as e:
        print(f"[WeatherBot] ZIP lookup failed: {e}")
        return None, None

def get_interface():
    try:
        return TCPInterface("127.0.0.1")
    except Exception as e:
        print(f"[WeatherBot] TCP error: {e}")
        return None

def send_to_meshtastic(chunks, channel_index):
    global interface
    for chunk in chunks:
        try:
            interface.sendText(chunk, channelIndex=channel_index)
            time.sleep(1)
        except BrokenPipeError:
            print("[WeatherBot] Broken pipe. Reinitializing...")
            interface = get_interface()

def split_message(text, max_len=MAX_MSG_LEN):
    words = text.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_len:
            current += word + " "
        else:
            chunks.append(current.strip())
            current = word + " "
    if current:
        chunks.append(current.strip())

    return [f"({i+1}/{len(chunks)}) {chunk}" for i, chunk in enumerate(chunks)]

def get_forecast(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode",
        "timezone": "America/Chicago"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[WeatherBot] Forecast error: {e}")
        return None

def summarize_current(data):
    temp_c = data['hourly']['temperature_2m'][0]
    temp = round((temp_c * 9/5) + 32)
    code = data['hourly']['weathercode'][0]
    emoji = WEATHER_CODES.get(code, "❓").split()[0]
    return f"Current weather: {emoji} {temp}°F"

def summarize_hourly(data):
    lines = ["Next 5 hours:"]
    for i in range(5):
        raw_time = data['hourly']['time'][i]
        dt = datetime.datetime.strptime(raw_time, "%Y-%m-%dT%H:%M")
        time_str = dt.strftime("%-I:%M %p")  # Use %#I for Windows
        temp_c = data['hourly']['temperature_2m'][i]
        temp = round((temp_c * 9/5) + 32)
        emoji = WEATHER_CODES.get(data['hourly']['weathercode'][i], "❓").split()[0]
        lines.append(f"{time_str} {emoji} {temp}°F")
    return "\n".join(lines)

def summarize_daily(data):
    lines = ["5-day forecast:"]
    for i in range(5):
        day = datetime.datetime.strptime(data['daily']['time'][i], "%Y-%m-%d").strftime('%a')
        tmin_c = data['daily']['temperature_2m_min'][i]
        tmax_c = data['daily']['temperature_2m_max'][i]
        tmin = round((tmin_c * 9/5) + 32)
        tmax = round((tmax_c * 9/5) + 32)
        emoji = WEATHER_CODES.get(data['daily']['weathercode'][i], "❓").split()[0]
        lines.append(f"{day} {emoji} {tmin}–{tmax}°F")
    return "\n".join(lines)

def get_weather_alerts(lat, lon):
    url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    try:
        res = requests.get(url, headers={"User-Agent": "WeatherBot/1.0"})
        res.raise_for_status()
        return res.json().get("features", [])
    except Exception as e:
        print(f"[WeatherBot] Alert fetch error: {e}")
        return []

def summarize_alert(alert):
    props = alert['properties']
    headline = props.get('headline', 'Alert')
    severity = props.get('severity', 'Unknown')
    event = props.get('event')
    return f"🚨 {severity.upper()} Alert: {event}\n{headline}"

def check_and_send_alerts(lat, lon, channel_index, sent_alerts):
    alerts = get_weather_alerts(lat, lon)
    now = time.time()
    new_sent = sent_alerts.copy()
    for alert in alerts:
        props = alert['properties']
        alert_id = alert['id']
        severity = props.get('severity', 'Unknown')
        interval = SEVERITY_INTERVALS.get(severity, 3600)
        if alert_id not in sent_alerts or now - sent_alerts[alert_id] >= interval:
            msg = summarize_alert(alert)
            send_to_meshtastic(split_message(msg), channel_index)
            new_sent[alert_id] = now
    save_sent_alerts(new_sent)
    return new_sent

def main():
    global interface
    settings = load_settings()
    channel_index = settings.get("channel_index", 0)
    zip_code = settings.get("zip")
    api_key = settings.get("api_key")
    lat, lon = resolve_zip_to_latlon(zip_code, api_key)
    interface = get_interface()
    sent_alerts = load_sent_alerts()

    print("[WeatherBot] Initial run...")
    forecast = get_forecast(lat, lon)
    if forecast:
        send_to_meshtastic(split_message(summarize_current(forecast)), channel_index)
        send_to_meshtastic(split_message(summarize_hourly(forecast)), channel_index)
        send_to_meshtastic(split_message(summarize_daily(forecast)), channel_index)
    sent_alerts = check_and_send_alerts(lat, lon, channel_index, sent_alerts)

    while True:
        now = datetime.datetime.now()
        if now.minute % 10 == 0 and now.second < 5:
            print(f"[WeatherBot] Scheduled update at {now.strftime('%H:%M:%S')}")
            forecast = get_forecast(lat, lon)
            if forecast:
                send_to_meshtastic(split_message(summarize_current(forecast)), channel_index)
                send_to_meshtastic(split_message(summarize_hourly(forecast)), channel_index)
                send_to_meshtastic(split_message(summarize_daily(forecast)), channel_index)
            sent_alerts = check_and_send_alerts(lat, lon, channel_index, sent_alerts)
            time.sleep(60)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
