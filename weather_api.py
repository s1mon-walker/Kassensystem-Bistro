import requests, json

def get_local_weather(city):
    api_key = ""
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    complete_url = base_url + "appid=" + api_key + "&q=" + city
    response = requests.get(complete_url)
    x = response.json()

    if x["cod"] != "404":

        y = x["main"]
        temp_min_kelvin = y["temp_min"]
        temp_max_kelvin = y["temp_max"]
        temp_min = int(temp_min_kelvin - 273.15)
        temp_max = int(temp_max_kelvin - 273.15)

        z = x["weather"]
        weather_description = z[0]["description"]

        return f'Wetter: {temp_min}°C - {temp_max}°C Beschreibung: {weather_description}'
    else:
        print(" City Not Found ")
        return 'Fehler: Keine Daten gefunden'

if __name__ == '__main__':
    weather = get_local_weather('schwyz')
    if weather:
        print(weather)
