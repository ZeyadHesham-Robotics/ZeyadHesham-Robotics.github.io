#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <LiquidCrystal_I2C.h>
#include <HX711.h>
#include <AccelStepper.h>

void updateLCD(void);

// WiFi credentials
const char *ssid = "ZAD LAB";
const char *password = "#Z2A0D #L2A4B #";

// Web server
WebServer server(8080);
// LCD setup (I2C) - 16x2 display
LiquidCrystal_I2C lcd(0x27, 16, 2);

// HX711 Load Cell
HX711 scale;

// ESP32 Control Pin Mapping
const int CONV1_STEP = 32, CONV1_DIR = 33;
const int CONV2_STEP = 25, CONV2_DIR = 26;
const int SP1_ROTATE_STEP = 14, SP1_ROTATE_DIR = 27;
const int SP1_PUSH_STEP = 12, SP1_PUSH_DIR = 13;
const int SP2_ROTATE_STEP = 2, SP2_ROTATE_DIR = 15;
const int SP2_PUSH_STEP = 16, SP2_PUSH_DIR = 4;

// Hardware pins
const int HX711_DT = 5, HX711_SCK = 18;
const int PLUS_BUTTON = 19, MINUS_BUTTON = 23, ENTER_BUTTON = 39;

// AccelStepper motors
AccelStepper conv1(AccelStepper::DRIVER, CONV1_STEP, CONV1_DIR);
AccelStepper conv2(AccelStepper::DRIVER, CONV2_STEP, CONV2_DIR);
AccelStepper sp1Rotate(AccelStepper::DRIVER, SP1_ROTATE_STEP, SP1_ROTATE_DIR);
AccelStepper sp1Push(AccelStepper::DRIVER, SP1_PUSH_STEP, SP1_PUSH_DIR);
AccelStepper sp2Rotate(AccelStepper::DRIVER, SP2_ROTATE_STEP, SP2_ROTATE_DIR);
AccelStepper sp2Push(AccelStepper::DRIVER, SP2_PUSH_STEP, SP2_PUSH_DIR);

AccelStepper *motors[] = {&conv1, &conv2, &sp1Rotate, &sp1Push, &sp2Rotate, &sp2Push};
const char *motorNames[] = {"Conv1", "Conv2", "SP1Rot", "SP1Push", "SP2Rot", "SP2Push"};

// System enums
enum SortingMode
{
  SORT_BY_COLOR,
  SORT_BY_WEIGHT,
  SORT_BY_SIZE
};
enum Direction
{
  STRAIGHT,
  LEFT,
  RIGHT
};
enum SortingPoint
{
  POINT_1,
  POINT_2
};

// Data structures
struct BoxData
{
  String color;
  float weight;
  String size;
  bool valid;
};

struct SortingRule
{
  String criteria;
  SortingPoint point;
  Direction direction;
};

// System state
SortingMode activeSortingMode = SORT_BY_COLOR;
String systemStatus = "READY";
BoxData currentBox;
bool isProcessing = false;
unsigned long processingStartTime = 0;
unsigned long lastLCDUpdate = 0;

// Sorting rules
SortingRule colorRules[] = {
    {"red", POINT_1, LEFT}, {"green", POINT_1, RIGHT}, {"blue", POINT_1, STRAIGHT}, {"yellow", POINT_2, LEFT}, {"orange", POINT_2, RIGHT}, {"purple", POINT_2, STRAIGHT}};

struct WeightRule
{
  float minWeight, maxWeight;
  SortingPoint point;
  Direction direction;
};

WeightRule weightRules[] = {
    {0, 100, POINT_1, LEFT}, {100, 300, POINT_1, RIGHT}, {300, 500, POINT_1, STRAIGHT}, {500, 1000, POINT_2, LEFT}, {1000, 9999, POINT_2, RIGHT}};

SortingRule sizeRules[] = {
    {"small", POINT_1, LEFT}, {"medium", POINT_1, RIGHT}, {"large", POINT_2, STRAIGHT}};

void initializeMotors()
{
  Serial.println("Initializing AccelStepper motors…");

  // Set motor speeds and accelerations
  for (int i = 0; i < 6; i++)
  {
    motors[i]->setMaxSpeed(1000);
    motors[i]->setAcceleration(500);
    motors[i]->setCurrentPosition(0);
    Serial.printf("Motor %s initialized\n", motorNames[i]);
  }

  Serial.println("All motors initialized!");
}

void initializeHardware()
{
  Serial.println("Initializing hardware…");

  // Button pins
  pinMode(PLUS_BUTTON, INPUT_PULLUP);
  pinMode(MINUS_BUTTON, INPUT_PULLUP);
  pinMode(ENTER_BUTTON, INPUT_PULLUP);

  // LCD
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SORTING SYSTEM");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  // Load cell
  scale.begin(HX711_DT, HX711_SCK);
  if (scale.is_ready())
  {
    scale.set_scale();
    scale.tare();
    Serial.println("HX711 ready");
  }

  Serial.println("Hardware initialized!");
}

void moveToSortingPoint(SortingPoint point)
{
  Serial.printf("Moving to sorting point % d\n", point + 1);
  systemStatus = "MOVING";
  updateLCD();

  if (point == POINT_1)
  {
    conv1.move(800);
    while (conv1.isRunning())
    {
      conv1.run();
      delay(1);
    }
  }
  else
  {
    conv1.move(800);
    while (conv1.isRunning())
    {
      conv1.run();
      delay(1);
    }
    delay(300);
    conv2.move(800);
    while (conv2.isRunning())
    {
      conv2.run();
      delay(1);
    }
  }
}

void rotateToDirection(SortingPoint point, Direction dir)
{
  if (dir == STRAIGHT)
    return;

  AccelStepper *rotateMotor = (point == POINT_1) ? &sp1Rotate : &sp2Rotate;
  int steps = (dir == LEFT) ? -100 : 100;

  Serial.printf("Rotating SP%d to %s\n", point + 1, (dir == LEFT) ? "LEFT" : "RIGHT");
  systemStatus = "ROTATING";
  updateLCD();

  rotateMotor->move(steps);
  while (rotateMotor->isRunning())
  {
    rotateMotor->run();
    delay(1);
  }
}

void pushBox(SortingPoint point)
{
  AccelStepper *pushMotor = (point == POINT_1) ? &sp1Push : &sp2Push;

  Serial.printf("Pushing box at SP%d\n", point + 1);
  systemStatus = "PUSHING";
  updateLCD();

  // Push forward
  pushMotor->move(200);
  while (pushMotor->isRunning())
  {
    pushMotor->run();
    delay(1);
  }

  delay(200);

  // Return
  pushMotor->move(-200);
  while (pushMotor->isRunning())
  {
    pushMotor->run();
    delay(1);
  }
}

void makeSortingDecision(BoxData box, SortingPoint &point, Direction &dir)
{
  point = POINT_1;
  dir = STRAIGHT;

  switch (activeSortingMode)
  {
  case SORT_BY_COLOR:
    for (int i = 0; i < 6; i++)
    {
      if (box.color.equalsIgnoreCase(colorRules[i].criteria))
      {
        point = colorRules[i].point;
        dir = colorRules[i].direction;
        break;
      }
    }
    break;

  case SORT_BY_WEIGHT:
    for (int i = 0; i < 5; i++)
    {
      if (box.weight >= weightRules[i].minWeight && box.weight < weightRules[i].maxWeight)
      {
        point = weightRules[i].point;
        dir = weightRules[i].direction;
        break;
      }
    }
    break;

  case SORT_BY_SIZE:
    for (int i = 0; i < 3; i++)
    {
      if (box.size.equalsIgnoreCase(sizeRules[i].criteria))
      {
        point = sizeRules[i].point;
        dir = sizeRules[i].direction;
        break;
      }
    }
    break;
  }

  Serial.printf("Decision: SP%d, %s\n", point + 1,
                dir == LEFT ? "LEFT" : dir == RIGHT ? "RIGHT"
                                                    : "STRAIGHT");
}

void processSorting(BoxData box)
{
  Serial.println("== = Starting Sorting Process == =");
  isProcessing = true;
  processingStartTime = millis();

  SortingPoint point;
  Direction dir;
  makeSortingDecision(box, point, dir);

  // Execute sorting sequence
  moveToSortingPoint(point);
  delay(500);
  rotateToDirection(point, dir);
  delay(300);
  pushBox(point);
  delay(300);

  // Reset rotation if needed
  if (dir != STRAIGHT)
  {
    rotateToDirection(point, STRAIGHT);
  }

  systemStatus = "COMPLETE";
  updateLCD();
  delay(1000);
  systemStatus = "READY";
  isProcessing = false;

  Serial.println("=== Sorting Complete ===");
}

void updateLCD()
{
  static int lcdPage = 0;
  static unsigned long lcdTimer = 0;

  if (millis() - lcdTimer > 3000)
  {
    lcdPage = (lcdPage + 1) % 2;
    lcdTimer = millis();
  }

  lcd.clear();

  if (lcdPage == 0)
  {
    lcd.setCursor(0, 0);
    String modes[] = {"COLOR", "WEIGHT", "SIZE"};
    lcd.print("MODE:" + modes[activeSortingMode]);
    lcd.setCursor(0, 1);
    lcd.print(systemStatus);
  }
  else
  {
    lcd.setCursor(0, 0);
    lcd.print("WiFi:" + String(WiFi.status() == WL_CONNECTED ? "OK" : "ERR"));
    lcd.setCursor(0, 1);
    if (WiFi.status() == WL_CONNECTED)
    {
      String ip = WiFi.localIP().toString();
      if (ip.length() > 16)
        ip = ip.substring(ip.length() - 16);
      lcd.print(ip);
    }
    else
    {
      lcd.print("Disconnected");
    }
  }
}

void checkButtons()
{
  static unsigned long lastPress = 0;
  if (millis() - lastPress < 200)
    return;

  if (digitalRead(PLUS_BUTTON) == LOW)
  {
    activeSortingMode = (SortingMode)((activeSortingMode + 1) % 3);
    updateLCD();
    lastPress = millis();
  }

  if (digitalRead(MINUS_BUTTON) == LOW)
  {
    activeSortingMode = (SortingMode)((activeSortingMode - 1 + 3) % 3);
    updateLCD();
    lastPress = millis();
  }
}

// Web server handlers
void handleProcessBox()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");
  server.sendHeader("Access - Control - Allow - Methods", "POST, OPTIONS");
  server.sendHeader("Access - Control - Allow - Headers", "Content - Type");

  if (server.method() == HTTP_OPTIONS)
  {
    server.send(200);
    return;
  }

  if (isProcessing)
  {
    server.send(409, "application/json", "{\"status\":\"error\",\"message\":\"System busy\"}");
    return;
  }

  if (!server.hasArg("plain"))
  {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"No data\"}");
    return;
  }

  JsonDocument doc(512);
  if (deserializeJson(doc, server.arg("plain")))
  {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
    return;
  }

  BoxData box;
  box.color = doc["color"].as<String>();
  box.weight = doc["weight"];
  box.size = doc["size"].as<String>();
  box.valid = true;

  currentBox = box;

  JsonDocument response(512);
  response["status"] = "success";
  response["message"] = "Processing started";
  response["boxData"]["color"] = box.color;
  response["boxData"]["weight"] = box.weight;
  response["boxData"]["size"] = box.size;

  String responseStr;
  serializeJson(response, responseStr);
  server.send(200, "application/json", responseStr);

  processSorting(box);
}

void handleStatus()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");

  JsonDocument status(1024);
  String modeNames[] = {"COLOR", "WEIGHT", "SIZE"};

  status["status"] = "success";
  status["sortingMode"] = modeNames[activeSortingMode];
  status["systemStatus"] = systemStatus;
  status["isProcessing"] = isProcessing;
  status["uptime"] = millis();

  status["network"]["connected"] = (WiFi.status() == WL_CONNECTED);
  if (WiFi.status() == WL_CONNECTED)
  {
    status["network"]["ip"] = WiFi.localIP().toString();
    status["network"]["rssi"] = WiFi.RSSI();
  }

  if (currentBox.valid)
  {
    status["currentBox"]["color"] = currentBox.color;
    status["currentBox"]["weight"] = currentBox.weight;
    status["currentBox"]["size"] = currentBox.size;
  }

  String response;
  serializeJson(status, response);
  server.send(200, "application/json", response);
}

void handleTest()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");

  if (isProcessing)
  {
    server.send(409, "application/json", "{\"status\":\"error\",\"message\":\"System busy\"}");
    return;
  }

  BoxData testBox = {"red", 150.0, "medium", true};
  currentBox = testBox;

  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Test started\"}");
  processSorting(testBox);
}

void handleEmergencyStop()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");

  Serial.println("EMERGENCY STOP");

  // Stop all motors immediately
  for (int i = 0; i < 6; i++)
  {
    motors[i]->stop();
    motors[i]->setCurrentPosition(motors[i]->currentPosition());
  }

  isProcessing = false;
  systemStatus = "EMERGENCY STOP";
  updateLCD();

  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Emergency stop activated\"}");
}

void handleReset()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");

  Serial.println("System reset");

  // Reset all motor positions
  for (int i = 0; i < 6; i++)
  {
    motors[i]->setCurrentPosition(0);
  }

  isProcessing = false;
  systemStatus = "READY";
  currentBox.valid = false;
  updateLCD();

  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"System reset\"}");
}

void handleRoot()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");

  JsonDocument info(512);
  info["system"] = "ESP32 Sorting Controller";
  info["version"] = "2.0.0";
  info["status"] = "operational";

  String modeNames[] = {"COLOR", "WEIGHT", "SIZE"};
  info["sortingMode"] = modeNames[activeSortingMode];
  info["isProcessing"] = isProcessing;

  JsonObject api = info.createNestedObject("endpoints");
  api["/"] = "System info (GET)";
  api["/status"] = "Status (GET)";
  api["/process"] = "Process box (POST)";
  api["/test"] = "Test sequence (POST)";
  api["/emergency-stop"] = "Emergency stop (POST)";
  api["/reset"] = "Reset (POST)";

  String response;
  serializeJson(info, response);
  server.send(200, "application/json", response);
}

void handleNotFound()
{
  server.sendHeader("Access - Control - Allow - Origin", "*");
  server.send(404, "application / json", "{" status " : " error ", " message " : " Not found "}");
}

void setupWiFi()
{
  Serial.println("Connecting to WiFi…");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20)
  {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.printf("\nWiFi connected! IP: %s\n", WiFi.localIP().toString().c_str());
  }
  else
  {
    Serial.println("\nWiFi failed - offline mode");
  }
}

void setupWebServer()
{
  server.on("/", HTTP_GET, handleRoot);
  server.on("/ status", HTTP_GET, handleStatus);
  server.on("/ process", HTTP_POST, handleProcessBox);
  server.on("/ process", HTTP_OPTIONS, handleProcessBox);
  server.on("/ test", HTTP_POST, handleTest);
  server.on("/ emergency - stop", HTTP_POST, handleEmergencyStop);
  server.on("/ reset", HTTP_POST, handleReset);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("Web server started on port 8080");
}

void setup()
{
  Serial.begin(115200);
  Serial.println("== = ESP32 Sorting System v2.0 == =");

  initializeHardware();
  initializeMotors();
  setupWiFi();
  setupWebServer();

  systemStatus = "READY";
  updateLCD();

  Serial.println("=== System Ready ===");
  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.printf("Python endpoint: http://%s:8080/process\n", WiFi.localIP().toString().c_str());
  }
}

void loop()
{
  // Handle web requests
  server.handleClient();

  // Run motors (AccelStepper background processing)
  for (int i = 0; i < 6; i++)
  {
    motors[i]->run();
  }

  // Check buttons
  checkButtons();

  // Update LCD periodically
  if (millis() - lastLCDUpdate > 1000)
  {
    updateLCD();
    lastLCDUpdate = millis();
  }

  // WiFi reconnection check
  static unsigned long lastWiFiCheck = 0;
  if (millis() - lastWiFiCheck > 30000)
  {
    if (WiFi.status() != WL_CONNECTED)
    {
      WiFi.reconnect();
    }
    lastWiFiCheck = millis();
  }

  // Processing timeout protection
  if (isProcessing && (millis() - processingStartTime > 30000))
  {
    Serial.println("Processing timeout - resetting");
    isProcessing = false;
    systemStatus = "READY";
  }

  delay(1);
}