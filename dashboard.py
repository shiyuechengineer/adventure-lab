#!/usr/bin/env python3

import time

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

base_url = 'https://api.meraki.com/api/v0'

# Webex Teams bot token
token = 'MzNkMzdjOTItNzNlOC00NTY0LTliNzItZWE3MDRmYmM2NDM5OTUyYzU3ODktYTU5_PF84_1eb65fdf-9643-417f-9974-ad72cae0e10f'
# Your email address on Webex Teams
email = 'shiychen@cisco.com'


# List the organizations that the user has privileges on
# https://api.meraki.com/api_docs#list-the-organizations-that-the-user-has-privileges-on
def get_user_orgs(api_key):
    get_url = f'{base_url}/organizations'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    response = requests.get(get_url, headers=headers)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# List the networks in an organization
# https://api.meraki.com/api_docs#list-the-networks-in-an-organization
def get_networks(api_key, org_id, configTemplateId=None, session=None):
    get_url = f'{base_url}/organizations/{org_id}/networks'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if configTemplateId:
        get_url += f'?configTemplateId={configTemplateId}'

    if session:
        response = session.get(get_url, headers=headers)
    else:
        response = requests.get(get_url, headers=headers)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Enable/Disable VLANs for the given network
# https://api.meraki.com/api_docs#enable/disable-vlans-for-the-given-network
def enable_vlans(api_key, net_id, enabled=True):
    put_url = f'{base_url}/networks/{net_id}/vlansEnabledState'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    payload = {'enabled': enabled}

    response = requests.put(put_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Create a network
# https://api.meraki.com/api_docs#create-a-network
def create_network(api_key, org_id, name, net_type='wireless', tags='', copyFromNetworkId=None, timeZone='America/Los_Angeles', session=None):
    post_url = f'{base_url}/organizations/{org_id}/networks'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if tags and type(tags) == list:
        tags = ' '.join(tags)

    vars = locals()
    params = ['name', 'tags', 'timeZone', 'copyFromNetworkId']
    payload = dict((k, vars[k]) for k in params if vars[k])
    payload['type'] = net_type

    if session:
        response = session.post(post_url, headers=headers, json=payload)
    else:
        response = requests.post(post_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Delete a network
# https://api.meraki.com/api_docs#delete-a-network
def delete_network(api_key, net_id):
    delete_url = f'{base_url}/networks/{net_id}'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    response = requests.delete(delete_url, headers=headers)
    return response.ok


# Blink the LEDs on a device
# https://api.meraki.com/api_docs#blink-the-leds-on-a-device
def blink_device(api_key, net_id, serial, duration=20, period=160, duty=50):
    post_url = f'{base_url}/networks/{net_id}/devices/{serial}/blinkLeds'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    vars = locals()
    params = ['duration', 'period', 'duty']
    payload = dict((k, vars[k]) for k in params)

    response = requests.post(post_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Generate a snapshot of what the camera sees at the specified time and return a link to that image.
# https://api.meraki.com/api_docs#generate-a-snapshot-of-what-the-camera-sees-at-the-specified-time-and-return-a-link-to-that-image
def take_snapshot(api_key, net_id, serial, timestamp=None):
    post_url = f'{base_url}/networks/{net_id}/cameras/{serial}/snapshot'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'} if timestamp else {'X-Cisco-Meraki-API-Key': api_key}

    payload = {'timestamp': timestamp} if timestamp else {}

    response = requests.post(post_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Try snapshot URL to see if ready, and if so, download to local disk
def try_snapshot(url, name):
    attempts = 10
    while attempts > 0:
        # print(attempts)
        r = requests.get(url, stream=True)
        if r.ok:
            temp_file = f'{name}.jpg'
            with open(temp_file, 'wb') as f:
                for chunk in r:
                    f.write(chunk)
            return temp_file
        else:
            time.sleep(1)
            attempts -= 1
    return None


# Return the inventory for an organization
# https://api.meraki.com/api_docs#return-the-inventory-for-an-organization
def get_inventory(api_key, org_id, session=None):
    get_url = f'{base_url}/organizations/{org_id}/inventory'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if session:
        response = session.get(get_url, headers=headers)
    else:
        response = requests.get(get_url, headers=headers)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Update the per-port VLAN settings for a single MX port
# https://api.meraki.com/api_docs#update-the-per-port-vlan-settings-for-a-single-mx-port
def update_mx_port(api_key, net_id, port, enabled=None, dropUntaggedTraffic=None,
                   type=None, vlan=None, allowedVlans=None, accessPolicy=None):
    put_url = f'{base_url}/networks/{net_id}/appliancePorts/{port}'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    vars = locals()
    params = ['enabled', 'dropUntaggedTraffic', 'type', 'vlan', 'allowedVlans', 'accessPolicy']
    payload = dict((k, vars[k]) for k in params if vars[k])

    response = requests.put(put_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# List the status of every Meraki device in the organization
# https://api.meraki.com/api_docs#list-the-status-of-every-meraki-device-in-the-organization
def get_device_statuses(api_key, org_id):
    get_url = f'{base_url}/organizations/{org_id}/deviceStatuses'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    response = requests.get(get_url, headers=headers)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Update an SSID to be open with name
# https://api.meraki.com/api_docs#update-the-attributes-of-an-ssid
def open_ssid(api_key, net_id, number, name):
    put_url = f'{base_url}/networks/{net_id}/ssids/{number}'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    payload = {
        'name': name,
        'enabled': True,
        'authMode': 'open',
    }

    response = requests.put(put_url, headers=headers, json=payload)
    data = response.json() if response.ok else response.text
    return (response.ok, data)


# Send a message in Webex Teams
def post_message(url, message):
    headers = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {token}'}
    payload = {'toPersonEmail': email, 'file': url, 'markdown': message}
    requests.post('https://api.ciscospark.com/v1/messages/', headers=headers, json=payload)


# Send a message with file attached from local storage
def send_file(message, file_path, file_type='text/plain'):
    # file_type such as 'image/png'
    m = MultipartEncoder({'toPersonEmail': email,
                          'markdown': message,
                          'files': (file_path, open(file_path, 'rb'),
                                    file_type)})
    r = requests.post('https://api.ciscospark.com/v1/messages', data=m,
                  headers={'Authorization': f'Bearer {token}', 'Content-Type': m.content_type})
    if r.ok:
        print(message)
    else:
        print(r.text)
