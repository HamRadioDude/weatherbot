# WeatherBot for Meshtastic

WeatherBot is a Python script that runs on a Raspberry Pi and sends real-time weather updates to your Meshtastic network using the OpenWeather API. It supports periodic forecasts, alert monitoring, and custom channel delivery.  It was originally written by me, and pieced together, then my Dog looked at it and said it looked "RUFF". We then hired AI to do better.  It did better.   Subscribe to Ham Radio Dude.

## Features

- Current weather updates with descriptions and temperatures
- Hourly and 5-day forecasts
- Weather alert detection (advisories, watches, warnings)
- Adaptive alert checking based on severity
- Runs autonomously every 10 minutes (configurable)
- Designed for Meshtastic message limits (chunked at 180 characters)
- Internet check with offline fallback messaging

## Requirements

- Raspberry Pi or compatible Linux system
- Python 3.7+
- OpenWeather API Key (free at openweathermap.org)
- Meshtastic TCP Interface running locally

## Setup

1. Clone this repository:
    ```bash
    git clone https://github.com/yourusername/weatherbot.git
    cd weatherbot
    ```

2. Install required Python libraries:
    ```bash
    pip install meshtastic requests
    ```

3. Create a `data/settings.json` file:
    ```json
    {
      "location": "00000,US",
      "api_key": "YOUR_API_KEY_HERE",
      "channel_index": 0
    }
    ```

4. Run the bot:
    ```bash
    python3 weatherbot.py
    ```

## Folder Structure

<pre>
weatherbot/
├── weatherbot.py
└── data/
    ├── settings.json
    └── alerts.json
</pre>

## Compatibility

This bot was developed and tested using a Raspberry Pi with the **MeshAdv PiHat** from MeshTastic Devices, which provides a clean UART connection via GPIO and includes automatic startup capabilities. It’s an ideal platform for permanent or low-power weather monitoring stations.

That said, **any Meshtastic-compatible node** can be used as long as:

- It is connected via USB to the Pi or host system
- The Meshtastic Python TCP server is running (`meshtastic --start`)
- The device appears as a serial interface to the system (e.g., `/dev/ttyUSB0`)

This makes the script flexible for use in both mobile and fixed installations.

## Notes

- The script uses OpenWeather's One Call API 3.0 for daily/hourly data.
- It converts city/ZIP into lat/lon using the OpenWeather Geo API.
- You can customize how often weather and alerts are checked.

## License

MIT License – Use freely, modify, contribute back if you like.
