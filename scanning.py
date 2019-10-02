import configparser
from datetime import datetime
import json
import os
import sys

from flask import Flask
from flask import request

app = Flask(__name__)

# Create folder for scanning API logs
if 'logs' not in os.listdir():
    os.mkdir('logs')


# Store credentials in a separate file
def gather_credentials():
    cp = configparser.ConfigParser()
    try:
        cp.read('credentials.ini')
        validator = cp.get('sense', 'validator')
        secret = cp.get('sense', 'secret')
    except:
        print('Missing credentials or input file!')
        sys.exit(2)
    return validator, secret


# Respond to Meraki with validator
@app.route('/', methods=['GET'])
def get_validator():
    print(f'VALIDATOR sent')
    return VALIDATOR, 200


# Accept scanning API JSON POST
@app.route('/', methods=['POST'])
def get_json():
    if not request.json or not 'data' in request.json:
        return 'invalid data', 400
    data = request.json
    print(f'Received POST: {data["type"]}, {data["version"]}')

    # Verify secret
    if data['secret'] != SECRET:
        print(f'Invalid secret: {data["secret"]}')
        return 'invalid secret', 403
    else:
        print(f'Secret verified: {data["secret"]}')

    # Save data locally to logs folder
    if data['type'] == 'BluetoothDevicesSeen':
        data_type = 'Bluetooth'
    else:
        data_type = 'WiFi'
    file_name = f'{datetime.now():%Y-%m-%d_%H-%M-%S}_{data_type}.json'
    with open(f'logs/{file_name}', 'w') as fp:
        json.dump(data, fp)
    print(f'Saved locally: {file_name}\n')

    # Delete any logs, keeping only the latest 100
    log_files = os.listdir('logs/')
    if len(log_files) > 100:
        log_files.sort()
        for file in log_files[:-100]:
            os.remove(f'logs/{file}')

    # Return success message
    return 'Scanning API POST received', 200


if __name__ == '__main__':
    # Get credentials and object count
    global VALIDATOR, SECRET
    (VALIDATOR, SECRET) = gather_credentials()

    # Run Flask application
    app.run(port=5000, debug=False)
