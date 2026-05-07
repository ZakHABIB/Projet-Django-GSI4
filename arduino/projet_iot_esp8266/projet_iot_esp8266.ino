#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <DHT.h>

#define DHTPIN D4
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

const char* ssid = "NOM_WIFI";
const char* password = "MOT_DE_PASSE_WIFI";

// PythonAnywhere: remplace zakar par ton nom d'utilisateur PythonAnywhere.
String serverName = "https://zakar.pythonanywhere.com/api/add/";

// Test local avant PythonAnywhere:
// String serverName = "http://192.168.1.10:8000/api/add/";

void setup() {
  Serial.begin(115200);
  dht.begin();

  Serial.println();
  Serial.println("Connexion WiFi...");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connecte");
  Serial.print("Adresse IP ESP8266: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    float temperature = dht.readTemperature();
    float humidite = dht.readHumidity();

    if (isnan(temperature) || isnan(humidite)) {
      Serial.println("Erreur lecture DHT11");
      delay(10000);
      return;
    }

    String data = "{\"temperature\":" + String(temperature, 1) +
                  ",\"humidite\":" + String(humidite, 1) + "}";

    Serial.println("Nouvelle mesure");
    Serial.println(data);

    HTTPClient http;
    int httpCode = 0;

    if (serverName.startsWith("https://")) {
      WiFiClientSecure client;
      client.setInsecure();
      http.begin(client, serverName);
    } else {
      WiFiClient client;
      http.begin(client, serverName);
    }

    http.addHeader("Content-Type", "application/json");
    httpCode = http.POST(data);

    Serial.print("Code HTTP: ");
    Serial.println(httpCode);

    if (httpCode > 0) {
      Serial.println(http.getString());
    } else {
      Serial.print("Erreur HTTP: ");
      Serial.println(http.errorToString(httpCode));
    }

    http.end();
  } else {
    Serial.println("WiFi deconnecte, reconnexion...");
    WiFi.begin(ssid, password);
  }

  delay(10000);
}
