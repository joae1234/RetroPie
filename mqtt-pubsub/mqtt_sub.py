import paho.mqtt.client as mqttClient
import time
import json
import ssl
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# Dados para conexão com Ubidots
connected = False
BROKER_ENDPOINT = "industrial.api.ubidots.com"
TLS_PORT = 8883
MQTT_USERNAME = os.getenv("UBIDOTS_TOKEN")
print("using token: " + MQTT_USERNAME)
MQTT_PASSWORD = MQTT_USERNAME
TOPIC = "/v1.6/devices/"
DEVICE_LABEL = "retropie"
TLS_CERT_PATH = "./industrial.pem"

# Definição de variaveis para definir subscribe
VARIABLE_LABEL = ["reqtemperatura", "reqcpu"]
sub1 = TOPIC + DEVICE_LABEL + "/" + VARIABLE_LABEL[0] + "/lv"
sub2 = TOPIC + DEVICE_LABEL + "/" + VARIABLE_LABEL[1] + "/lv"
MQTT_TOPICS = [(sub1, 0), (sub2, 0)]


def on_connect(client, userdata, flags, rc):
    global connected
    if rc == 0:

        print("[INFO] Connected to broker")
        connected = True
        client.subscribe(MQTT_TOPICS)
    else:
        print(f"[INFO] Error, connection failed. Return Code rc = {rc}")
        print(f"Error flags: {flags}")


def on_message(client, userdata, msg):
    topic = msg.topic

    try:
        data = json.loads(msg.payload)
        print(data)

        if "reqtemperatura" in topic:
            send_temperature(data)
        elif "reqcpu" in topic:
            send_cpu(data)
            print("CPU: ", data)

    except Exception as e:
        print(e)


def send_temperature(data):
    data = int(data)

    if data == 0: # Enviar temperatura apenas quando botão for ON
        return

    # Rodar script para pegar temperatura antes

    temperatura = subprocess.run(["cat", "/sys/class/thermal/thermal_zone0/temp"], capture_output=True, text=True).stdout
    print("antes do int: " + temperatura)
    temperatura = int(temperatura) / 1000

    subprocess.run(["python3", "mqtt_publisher.py", "-v", str(temperatura), "-l", "temperatura"]) # Executa comando
    # Por conta do sleep do mqtt_publisher.py, pode atrasar caso chame CPU em seguida 
    # --> Ver se é possível executar em segundo plano

def send_cpu(data):
    data = int(data)

    if data == 0:
        return

    # Rodar script para pegar % cpu antes

    result = subprocess.run(["top", "-bn1"], capture_output=True, text=True).stdout

    for line in result.splitlines():
        if "Cpu(s)" in line:
            usage = line.split()
            cpu = float(usage[1]) + float(usage[3])
            break

    subprocess.run(["python3", "mqtt_publisher.py", "-v", str(cpu), "-l", "usocpu"]) # Executa comando
    # Por conta do sleep do mqtt_publisher.py, pode atrasar caso chame Temperatura em seguida 
    # --> Ver se é possível executar em segundo plano


def connect(mqtt_client, mqtt_username, mqtt_password, broker_endpoint, port):
    global connected  # Use global variable

    if not connected:
        mqtt_client.username_pw_set(mqtt_username, password=mqtt_password)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.tls_set(ca_certs=TLS_CERT_PATH,
                            certfile=None,
                            keyfile=None,
                            cert_reqs=ssl.CERT_REQUIRED,
                            tls_version=ssl.PROTOCOL_TLSv1_2,
                            ciphers=None)
        mqtt_client.tls_insecure_set(False)
        mqtt_client.connect(broker_endpoint, port=port)
        mqtt_client.loop_start()

        attempts = 0

        while not connected and attempts < 5:
            print("connected: " + str(connected))
            time.sleep(5)
            attempts += 1

        if not connected:
            print("[ERROR] Could not connect to broker. Aborting...")
            return False

    return True


if __name__ == "__main__":
    mqtt_client = mqttClient.Client()
    connect(mqtt_client, MQTT_USERNAME, MQTT_PASSWORD, BROKER_ENDPOINT,
            TLS_PORT)

    while True:
        time.sleep(1)
