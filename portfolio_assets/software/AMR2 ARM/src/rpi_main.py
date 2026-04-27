from flask import Flask, render_template_string, request, redirect, url_for
import serial
import time

SERIAL_PORT = '/dev/ttyUSB0'  # or '/dev/ttyACM0' if that's your ESP32 portBAUDRATE = 9600

COMMANDS = {
    'Enable Arm': 'z',
    'Disable Arm': 'x',
    'Base +': 'w',
    'Base -': 's',
    'Shoulder +': 'a',
    'Shoulder -': 'd',
    'Elbow +': 'q',
    'Elbow -': 'e',
    'Gripper Open': 'i',
    'Gripper Close': 'o'
}

app = Flask(__name__)
ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
time.sleep(2)  # Wait for ESP32 to reset

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Arm Control GUI</title>
    <style>
        body { font-family: Arial; text-align: center; }
        button { width: 150px; height: 50px; margin: 10px; font-size: 18px; }
        .row { margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>ESP32 Arm Control</h1>
    <form method="post">
        <div class="row">
            <button name="cmd" value="Enable Arm">Enable Arm</button>
            <button name="cmd" value="Disable Arm">Disable Arm</button>
        </div>
        <div class="row">
            <button name="cmd" value="Base +">Base +</button>
            <button name="cmd" value="Base -">Base -</button>
        </div>
        <div class="row">s
            <button name="cmd" value="Shoulder +">Shoulder +</button>
            <button name="cmd" value="Shoulder -">Shoulder -</button>
        </div>
        <div class="row">
            <button name="cmd" value="Elbow +">Elbow +</button>
            <button name="cmd" value="Elbow -">Elbow -</button>
        </div>
        <div class="row">
            <button name="cmd" value="Gripper Open">Gripper Open</button>
            <button name="cmd" value="Gripper Close">Gripper Close</button>
        </div>
    </form>
    {% if response %}
    <div>
        <h3>ESP32 Response:</h3>
        <pre>{{ response }}</pre>
    </div>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    response = ""
    if request.method == 'POST':
        cmd_label = request.form['cmd']
        cmd = COMMANDS.get(cmd_label)
        if cmd:
            ser.write(cmd.encode())
            time.sleep(0.1)
            while ser.in_waiting:
                response += ser.readline().decode(errors='ignore')
    return render_template_string(HTML, response=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)