import configparser
from datetime import datetime, timedelta
import json
import os
import sys

import requests

from chatbot import *
from snapshot import *


# Store credentials in a separate file
def gather_credentials():
    cp = configparser.ConfigParser()
    try:
        cp.read('credentials.ini')
        cam_key = cp.get('meraki', 'key2')
        org_id = cp.get('meraki', 'organization')
        chatbot_token = cp.get('chatbot', 'token')
        user_email = cp.get('chatbot', 'email')
        mv_serial = cp.get('sense', 'serial')
        home_macs = cp.get('sense', 'home')
    except:
        print('Missing credentials or input file!')
        sys.exit(2)
    return cam_key, org_id, chatbot_token, user_email, mv_serial, home_macs


# List the devices in an organization
def get_net_clients(session, api_key, net_id, start_time):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/networks/{net_id}/clients?perPage=1000&t0={start_time}', headers=headers)
    return response.json()


# Main function
if __name__ == '__main__':
    # Get credentials and object count
    (api_key, org_id, chatbot_token, user_email, mv_serial, home_macs) = gather_credentials()
    count = int(sys.argv[1])
    net_id = sys.argv[2]
    mv_name = sys.argv[3]

    # Establish session
    session = requests.Session()

    # Check if home devices have been seen in the last 5 minutes, via network-wide clients
    if home_macs:
        home_macs = home_macs.split(',')
        home_macs = [mac.strip().lower() for mac in home_macs]
        time_now = datetime.now()
        just_now = time_now - timedelta(minutes=5)
        start_time = datetime.isoformat(just_now) + 'Z'
        clients = get_net_clients(session, api_key, net_id, start_time)
        client_macs = [c['mac'] for c in clients]
        seen = set(home_macs).intersection(client_macs)

        # If so, no need to alert and exit
        if seen:
            print('MUTED!! Home MACs found via network-wide clients')
            sys.exit(0)

    # Check if home devices have been seen in the last 5 minutes, via scanning API
    if 'logs' in os.listdir():
        logs = [file for file in os.listdir('logs') if '.json' in file]
        recent_logs = []
        time_now = datetime.now()
        just_now = time_now - timedelta(minutes=5)
        for log in logs:
            log_time = datetime.strptime(log[:-5], '%Y-%m-%d_%H-%M-%S')
            if log_time > just_now:
                recent_logs.append(log)
        if recent_logs:
            for log in recent_logs:
                file_path = 'logs/' + log
                with open(file_path) as fp:
                    data = json.load(fp)
                client_macs = [c['clientMac'] for c in data['data']['observations']]
                seen = set(home_macs).intersection(client_macs)

                # If so, no need to alert and exit
                if seen:
                    print('MUTED!! Home MACs found via scanning API')
                    sys.exit(0)

    # Format message
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {chatbot_token}'
    }
    payload = {
        'toPersonEmail': user_email,
    }
    plural = 'person' if count == 1 else 'people'
    message = f'**{count} {plural}** seen by MV camera _{mv_name}_'

    # Generate snapshot and send
    file_url = generate_snapshot(api_key, net_id, mv_serial, session=session)
    if file_url:  # download/GET image from URL
        temp_file = download_file(session, mv_name, file_url)
        if temp_file:
            send_file(session, headers, payload, message, temp_file, file_type='image/jpg')
        else:
            message += ' (snapshot unsuccessfully retrieved)'
            post_message(session, headers, payload, message)
    else:
        message += ' (snapshot unsuccessfully requested)'
        post_message(session, headers, payload, message)
