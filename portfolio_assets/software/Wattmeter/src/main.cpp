#include <U8g2lib.h>
#include <Arduino.h>
#include "../include/PINOUT.h"
#include "../lib/ACS712.c"
#include "../lib/ZMPT101B.c"
#include <WiFi.h>
#include <WebServer.h>
U8G2_ST7920_128X64_F_SW_SPI u8g2(U8G2_R0, CLK, DATA, CS, RST);

void drawScreen(float voltage, float current, float power);
void drawDial(float value, float maxValue, const char *unit, int cx, int cy);
void handleRoot();
void handleData();
void showWaitToConnectScreen(void);

const char *ssid = "INVERTER_WIFI"; // Replace with your WiFi SSID
const char *password = "inverter_password";
float costPerKWh = 2;   // Set your electricity cost
float energy_kWh = 0.0; // Accumulated energy in kWh
WebServer server(80);

void setup()
{
  Serial.begin(9600);
  analogReadResolution(12);
  u8g2.begin();
  u8g2.setFont(u8g2_font_6x12_tr);
  u8g2.setBusClock(400000); // Lower bus speed for stability
  showWaitToConnectScreen();
  WiFi.softAP(ssid, password); // Start as Access Point
  while (WiFi.softAPgetStationNum() == 0)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/data", handleData);
  server.begin();
}

void loop()
{
  float voltageRMS = readACVoltage();
  float currentRMS = readACCurrent();
  float power = voltageRMS * currentRMS;

  static unsigned long lastTime = millis();
  unsigned long now = millis();
  float dt_h = (now - lastTime) / 3600000.0; // hours
  lastTime = now;
  energy_kWh += (power * dt_h) / 1000.0; // kWh

  Serial.printf("Voltage: %.2f V | Current: %.3f A | Power: %.2f W | Energy: %.4f kWh\n", voltageRMS, currentRMS, power, energy_kWh);
  Serial.printf("Cost:%.2f\n", energy_kWh * costPerKWh);

  u8g2.firstPage();
  do
  {
    drawScreen(voltageRMS, currentRMS, power);

    char buf[32];
    float cost = energy_kWh * costPerKWh;
    snprintf(buf, sizeof(buf), "Cost:%.2f", cost);
    u8g2.setFont(u8g2_font_6x10_tf);
    u8g2.setCursor(5, 22);
    u8g2.print(buf);

  } while (u8g2.nextPage());

  server.handleClient(); // important!

  delay(200);
}

/*
++++++++++++++++++++++++++++++++++++++++++++++++++++ GUI SECTION ++++++++++++++++++++++++++++++++++++++++++++++++++++
*/

void drawScreen(float voltage, float current, float power)
{
  // Thick frame (double borders)
  u8g2.drawFrame(0, 0, 128, 64);
  u8g2.drawFrame(1, 1, 126, 62);

  // Title (centered)
  const char *title = "POWER MONITOR";
  u8g2.setFont(u8g2_font_6x10_tf);
  int titleWidth = u8g2.getStrWidth(title);
  u8g2.setCursor((128 - titleWidth) / 2, 10);
  u8g2.print(title);

  // Power value (moved up center)
  char buf[10];
  dtostrf(power, 5, 1, buf);
  u8g2.setCursor(70, 22);
  u8g2.print("P:");
  u8g2.print(buf);
  u8g2.print("W");

  // Dials
  drawDial(voltage, 250.0, "V", 32, 44); // Voltage (left)
  drawDial(current, 30.0, "A", 96, 44);  // Current (right)
}

void drawDial(float value, float maxValue, const char *unit, int cx, int cy)
{
  // Draw thick arc (150° to 30°, clockwise — 0 on left)
  for (int r = 11; r <= 13; r++)
  { // Arc thickness
    for (int a = 150; a >= 30; a -= 2)
    {
      int x = cx + cos(radians(a)) * r;
      int y = cy - sin(radians(a)) * r;
      u8g2.drawPixel(x, y);
    }
  }

  // Needle calculation (reverse angle)
  float angle = map(value, 0, maxValue, 150, 30); // Left to right
  int nx = cx + cos(radians(angle)) * 10;
  int ny = cy - sin(radians(angle)) * 10;
  u8g2.drawLine(cx, cy, nx, ny);

  // Value label under the dial
  char buf[10];
  dtostrf(value, 4, 1, buf);
  strcat(buf, unit);
  u8g2.setFont(u8g2_font_5x8_tf);
  int tw = u8g2.getStrWidth(buf);
  u8g2.setCursor(cx - tw / 2, cy + 12);
  u8g2.print(buf);
}

void showWaitToConnectScreen()
{
  u8g2.clearBuffer();

  // Draw text below the QR
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.setCursor((128 - u8g2.getStrWidth("Connect to Start")) / 2, 30);
  u8g2.print("Connect to Start");

  u8g2.setCursor((128 - u8g2.getStrWidth("http://192.168.4.1")) / 2, 40);
  u8g2.print("http://192.168.4.1");

  u8g2.sendBuffer();
}

/*
++++++++++++++++++++++++++++++++++++++++++++++++++++ WEB SECTION ++++++++++++++++++++++++++++++++++++++++++++++++++++
*/
void handleRoot()
{
  String html = R"rawliteral(
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Offline Power Monitor</title>
    <style>
      body { background:#fff; color:#22223b; font-family: 'Segoe UI', monospace; text-align:center; margin:0; padding:0;}
      h1 { font-size:2em; margin:24px 0 12px; color:#22c55e; }
      .gauges { display:flex; justify-content:center; gap:24px; flex-wrap:wrap; margin-bottom:16px;}
      .gauge-card { background:#e5e7eb; border-radius:16px; padding:16px; box-shadow:0 4px 16px #0002; position:relative; }
      canvas { background:#f3f4f6; margin:10px; border-radius:8px; }
      .gauge-value { position:absolute; top:48px; left:0; width:100%; font-size:1.5em; color:#22c55e; font-weight:bold; text-align:center; pointer-events:none;}
      .gauge-label { margin-top:4px; font-size:1em; color:#22223b; }
      .chart-container { margin:24px auto; max-width:640px; background:#e5e7eb; border-radius:16px; padding:16px;}
      .cost { font-size:1.3em; color:#fbbf24; margin:18px 0 8px; font-weight:bold; }
      .summary { margin:18px auto 8px; max-width:400px; background:#e5e7eb; border-radius:12px; padding:12px; color:#22223b; }
      .btn { background:#38bdf8; color:#fff; padding:10px 24px; border:none; border-radius:8px; cursor:pointer; margin-top:18px; font-size:1em; font-weight:bold; }
      .btn:hover { background:#22c55e; color:#fff; }
      @media (max-width:700px) {
        .gauges { flex-direction:column; gap:12px; }
        .chart-container { padding:6px; }
      }
    </style>
  </head>
  <body>
    <h1>Offline Power Monitor</h1>
    <div class="summary">
      <div><b>Live readings:</b></div>
      <div>Voltage: <span id="voltVal">—</span> V</div>
      <div>Current: <span id="currVal">—</span> A</div>
      <div>Power: <span id="powerVal">—</span> W</div>
      <div>Energy: <span id="energyVal">—</span> kWh</div>
      <div class="cost" id="cost">Cost: —</div>
    </div>
    <div class="gauges">
      <div class="gauge-card">
        <span class="gauge-value" id="gaugeVoltVal">—</span>
        <canvas id="gaugeVolt" width="180" height="140"></canvas>
        <div class="gauge-label">Voltage</div>
      </div>
      <div class="gauge-card">
        <span class="gauge-value" id="gaugeCurrVal">—</span>
        <canvas id="gaugeCurr" width="180" height="140"></canvas>
        <div class="gauge-label">Current</div>
      </div>
      <div class="gauge-card">
        <span class="gauge-value" id="gaugePowerVal">—</span>
        <canvas id="gaugePower" width="180" height="140"></canvas>
        <div class="gauge-label">Power</div>
      </div>
    </div>
    <div class="chart-container">
      <canvas id="chart" width="600" height="200"></canvas>
    </div>
    <button class="btn" onclick="downloadCSV()">Download CSV</button>

    <script>
      function drawGauge(canvasId, value, max, label) {
        const c = document.getElementById(canvasId);
        const ctx = c.getContext('2d');
        ctx.clearRect(0,0,c.width,c.height);
        // Arc
        ctx.beginPath();
        ctx.arc(c.width/2, c.height-30, 50, Math.PI, 2*Math.PI);
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 8;
        ctx.stroke();
        // Needle
        const angle = Math.PI + (value/max)*Math.PI;
        const nx = c.width/2 + Math.cos(angle)*50;
        const ny = c.height-30 + Math.sin(angle)*50;
        ctx.beginPath();
        ctx.moveTo(c.width/2, c.height-30);
        ctx.lineTo(nx, ny);
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 4;
        ctx.stroke();
      }

      const times = [], powers = [], voltages = [], currents = [], energies = [];
      const logData = [];

      function drawChart() {
        const c = document.getElementById('chart');
        const ctx = c.getContext('2d');
        ctx.clearRect(0,0,c.width,c.height);
        // Axes
        ctx.strokeStyle = "#ccc";
        ctx.beginPath();
        ctx.moveTo(40,10); ctx.lineTo(40,190); ctx.lineTo(590,190);
        ctx.stroke();
        // Power curve
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for(let i=0;i<powers.length;i++){
          const x = 40 + (550 * i / Math.max(1,powers.length-1));
          const y = 190 - (powers[i]/Math.max(...powers,1))*160;
          if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        }
        ctx.stroke();
        // Numbers on curve
        ctx.font = "12px Segoe UI";
        ctx.fillStyle = "#22223b";
        for(let i=0;i<powers.length;i+=Math.max(1,Math.floor(powers.length/10))){
          const x = 40 + (550 * i / Math.max(1,powers.length-1));
          const y = 190 - (powers[i]/Math.max(...powers,1))*160;
          ctx.fillText(powers[i].toFixed(0), x, y-8);
        }
        // Labels
        ctx.font = "12px Segoe UI";
        ctx.fillStyle = "#38bdf8";
        ctx.fillText("Power (W)", 50, 24);
        ctx.fillStyle = "#22223b";
        ctx.fillText("Time", 540, 185);
      }

      function fetchData() {
        fetch('/data').then(r => r.json()).then(d => {
          drawGauge('gaugeVolt', d.voltage, 250, 'V');
          drawGauge('gaugeCurr', d.current, 50, 'A');
          drawGauge('gaugePower', d.power, 12500, 'W');

          // Numbers above gauges
          document.getElementById('gaugeVoltVal').textContent = d.voltage.toFixed(2) + " V";
          document.getElementById('gaugeCurrVal').textContent = d.current.toFixed(2) + " A";
          document.getElementById('gaugePowerVal').textContent = d.power.toFixed(2) + " W";

          document.getElementById('voltVal').textContent = d.voltage.toFixed(2);
          document.getElementById('currVal').textContent = d.current.toFixed(2);
          document.getElementById('powerVal').textContent = d.power.toFixed(2);
          document.getElementById('energyVal').textContent = (d.energy || 0).toFixed(4);
          document.getElementById('cost').textContent = "Cost: EGP" + d.cost.toFixed(2);

          const t = new Date().toLocaleTimeString();
          times.push(t); powers.push(d.power); voltages.push(d.voltage); currents.push(d.current); energies.push(d.energy || 0);
          if (times.length > 100) { times.shift(); powers.shift(); voltages.shift(); currents.shift(); energies.shift(); }
          logData.push({time: t, ...d});
          drawChart();
        }).catch(e => console.error(e));
      }

      function downloadCSV() {
        let csv = 'time,voltage,current,power,energy,cost\n';
        logData.forEach(r => csv += `${r.time},${r.voltage},${r.current},${r.power},${r.energy || 0},${r.cost}\n`);
        const b = new Blob([csv], {type:'text/csv'});
        const url = URL.createObjectURL(b);
        const a = document.createElement('a');
        a.href = url; a.download = 'power_log.csv'; a.click();
        URL.revokeObjectURL(url);
      }

      setInterval(fetchData, 1000);
      fetchData();
    </script>
  </body>
  </html>
  )rawliteral";

  server.send(200, "text/html", html);
}

void handleData()
{
  float voltage = readACVoltage();
  float current = readACCurrent();
  float power = voltage * current;
  float cost = energy_kWh * costPerKWh;

  String json = "{";
  json += "\"voltage\":" + String(voltage, 2) + ",";
  json += "\"current\":" + String(current, 2) + ",";
  json += "\"power\":" + String(power, 2) + ",";
  json += "\"energy\":" + String(energy_kWh, 4) + ",";
  json += "\"cost\":" + String(cost, 2);
  json += "}";

  server.send(200, "application/json", json);
}
