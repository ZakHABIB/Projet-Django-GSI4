#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <DHT.h>

// ============================================
// CONFIGURATION
// ============================================
const char* ssid = "Et@ehei";              // ← REMPLACEZ
const char* password = "eheio2023";
String serverName = "https://medakram.pythonanywhere.com/api/mesure/"; // ← REMPLACEZString serverName = "https://medakram.pythonanywhere.com/api/mesure/";
String nomPiece = "Salon";

#define DHTPIN D1
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

float temperature = 0;
float humidite = 0;
unsigned long lastSend = 0;
const unsigned long sendInterval = 30000;  // 30 secondes
int tentativesEchec = 0;

void setup() {
  Serial.begin(115200);
  delay(10);
  
  Serial.println();
  Serial.println("=================================");
  Serial.println("DÉMARRAGE DU CAPTEUR IoT");
  Serial.println("=================================");
  
  dht.begin();
  Serial.println("✅ Capteur DHT initialisé");
  
  // Configuration WiFi robuste
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  
  connecterWiFi();
}

void connecterWiFi() {
  Serial.print("🔌 Connexion au WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int tentatives = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    tentatives++;
    
    if (tentatives > 40) {
      Serial.println();
      Serial.println("❌ ÉCHEC: Impossible de se connecter au WiFi");
      Serial.println("Vérifiez votre SSID et mot de passe");
      return;
    }
  }
  
  Serial.println();
  Serial.println("✅ WiFi connecté !");
  Serial.print("📡 Adresse IP ESP8266: ");
  Serial.println(WiFi.localIP());
  Serial.print("🌐 Serveur: ");
  Serial.println(serverName);
  Serial.println("=================================");
}

void loop() {
  // Vérification WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi déconnecté, reconnexion...");
    connecterWiFi();
    delay(5000);
    return;
  }
  
  // Envoi périodique
  if (millis() - lastSend >= sendInterval) {
    lastSend = millis();
    
    // Lecture du capteur
    humidite = dht.readHumidity();
    temperature = dht.readTemperature();
    
    if (isnan(humidite) || isnan(temperature)) {
      Serial.println("❌ Erreur lecture capteur");
      return;
    }
    
    Serial.println("---------------------------------");
    Serial.print("🌡️ Température: ");
    Serial.print(temperature);
    Serial.print(" °C, 💧 Humidité: ");
    Serial.print(humidite);
    Serial.println(" %");
    
    // Envoi avec gestion d'erreur
    if (envoyerDonnees(temperature, humidite)) {
      tentativesEchec = 0;  // Réinitialiser le compteur
    } else {
      tentativesEchec++;
      Serial.print("⚠️ Échec d'envoi #");
      Serial.println(tentativesEchec);
      
      if (tentativesEchec >= 3) {
        Serial.println("🔄 Trop d'échecs, reconnexion WiFi...");
        WiFi.disconnect();
        delay(1000);
        connecterWiFi();
        tentativesEchec = 0;
      }
    }
  }
}

bool envoyerDonnees(float temp, float hum) {
  WiFiClientSecure *client = new WiFiClientSecure;
  
  // Configuration SSL
  client->setInsecure();
  client->setTimeout(10000);  // 10 secondes max
  
  HTTPClient http;
  http.setTimeout(15000);
  
  Serial.print("📤 Envoi: ");
  Serial.println(serverName);
  
  bool succes = false;
  
  if (http.begin(*client, serverName)) {
    http.addHeader("Content-Type", "application/json");
    
    String jsonData = "{";
    jsonData += "\"piece\":\"" + nomPiece + "\",";
    jsonData += "\"temperature\":" + String(temp) + ",";
    jsonData += "\"humidite\":" + String(hum);
    jsonData += "}";
    
    Serial.print("📦 Données: ");
    Serial.println(jsonData);
    
    int httpCode = http.POST(jsonData);
    
    if (httpCode > 0) {
      Serial.print("✅ Code réponse: ");
      Serial.println(httpCode);
      
      if (httpCode == 200 || httpCode == 201) {
        String reponse = http.getString();
        Serial.print("📨 Réponse: ");
        Serial.println(reponse);
        Serial.println("✅ Données envoyées !");
        succes = true;
      } else {
        Serial.print("❌ Code erreur: ");
        Serial.println(httpCode);
      }
    } else {
      Serial.print("❌ Erreur d'envoi: ");
      Serial.println(http.errorToString(httpCode).c_str());
    }
    
    http.end();
  } else {
    Serial.println("❌ Impossible de se connecter au serveur");
  }
  
  delete client;
  Serial.println("---------------------------------");
  return succes;
}
