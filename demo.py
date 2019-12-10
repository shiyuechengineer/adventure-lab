#!/usr/bin/env python3

import configparser
import csv
from datetime import datetime
import glob
import json
from json.decoder import JSONDecodeError
import os
import random
import time
import sys

from dashboard import *
from action_batches import *
from group_policies import policies
from group_policies_z import policies_z


# Webex Teams information if not storing in separate credentials.ini file
BOT_TOKEN = ''
USER_EMAIL = ''


# Create networks using action batches
def create_networks(api_key, org_id, sites, locations, custom_tags, time_zones):
    # See if "Demo - ISP" exists
    demo_isp = False
    (ok, data) = get_networks(api_key, org_id)
    if not ok:
        sys.exit(data)
    net_names = [network['name'] for network in data]
    if 'Demo - ISP' in net_names:
        demo_isp = True
        demo_net = data[net_names.index('Demo - ISP')]['id']
    else:
        # Create base network with VLANs enabled
        net_type = 'appliance switch wireless camera'
        (ok, data) = create_network(api_key, org_id, f'Demo {datetime.now():%Y-%m-%d_%H-%m-%S}', net_type)
        demo_net = data['id']
    (ok, data) = enable_vlans(api_key, demo_net, True)

    # Use action batch to create actual demo networks, cloning from base
    net_type = 'appliance switch wireless camera'
    actions = []
    for (site, location, time_zone) in zip(sites, locations, time_zones):
        net_name = location
        net_tags = ' '.join(random.sample(custom_tags + ['foo', 'bar', 'foobar', 'spam', 'ham', 'eggs'], 3))
        action = {
            'name': f'{net_name}',
            'type': net_type,
            'tags': net_tags,
            'copyFromNetworkId': demo_net,
            'timeZone': time_zone
        }
        actions.append({
            'resource': f'/organizations/{org_id}/networks',
            'operation': 'create',
            'body': action
        })

    # Output action batch JSON, if needed for Postman
    with open('create_networks.json', 'w') as fp:
        payload = {
            'confirmed': True,
            'synchronous': True,
            'actions': actions
        }
        json.dump(payload, fp)

    # Run API call
    print('Data to create networks generated in the create_networks.json file. Do you want to run the API call using\n1) Python script here or')
    stop = input('2) in Postman manually? ')
    if '2' in stop or 'postman' in stop.lower():
        input('Hit ENTER to continue only after manual POST is successful...')
    else:
        print('POSTing one synchronous action batch to create networks using payload from create_networks.json...')
        (ok, data) = create_action_batch(api_key, org_id, True, True, actions)
        if not ok:
            sys.exit(data)
        else:
            batch_id = data['id']
            print(f'Action batch {batch_id} completed!')

    # Remove unneeded base network that was created at beginning
    if not demo_isp:
        delete_network(api_key, demo_net)


# Helper function to claim devices
def add_devices(actions, net_id, serial):
    if serial:
        actions.append(
            {
                'resource': f'/networks/{net_id}/devices',
                'operation': 'claim',
                'body': {
                    'serial': serial
                }
            }
        )


# Create/claim devices using action batches
def create_devices(api_key, org_id, actions):
    with open('create_devices.json', 'w') as fp:
        payload = {
            'confirmed': True,
            'synchronous': False,
            'actions': actions
        }
        json.dump(payload, fp)

    # Run API call
    print('Data to add devices generated in the create_devices.json file. Do you want to run the API call using\n1) Python script here or')
    stop = input('2) in Postman manually? ')
    if '2' in stop or 'postman' in stop.lower():
        input('Hit ENTER once manual POST is successful...')
    else:
        print('POSTing one asynchronous action batch to claim devices, payload in create_devices.json...')
        (ok, data) = create_action_batch(api_key, org_id, True, False, actions)
        if not ok:
            print(data)
        else:
            batch_id = data['id']
            done = check_until_completed(api_key, org_id, batch_id)

    # Check status and return completion success


# Helper function to configure devices' attributes
def configure_device(actions, net_id, serial, name, address, user_name, custom_tags):
    if serial:
        actions.append(
            {
                'resource': f'/networks/{net_id}/devices/{serial}',
                'operation': 'update',
                'body': {
                    'name': name,
                    'tags': ' '.join(random.sample(custom_tags + ['foo', 'bar', 'foobar', 'spam', 'ham', 'eggs'], 3)),
                    'address': address,
                    'moveMapMarker': True,
                    'notes': f'installed by {user_name}'
                }
            }
        )


# Helper fucntion to configure MX's port 3
def batch_mx_port(actions, net_id, mgmt_vlan, port=3):
    action = {
        'resource': f'/networks/{net_id}/appliancePorts/{port}',
        'operation': 'update',
        'body': {
            'enabled': True,
            'type': 'trunk',
            'dropUntaggedTraffic': False,
            'vlan': mgmt_vlan,
            'allowedVlans': 'all'
        }
    }
    actions.append(action)


# Helper function configure devices' management IP addresses
def batch_devices(actions, net_id, serials_ips, vlan):
    for (serial, ip) in serials_ips:
        if serial:
            action = {
                'resource': f'/networks/{net_id}/devices/{serial}/managementInterfaceSettings',
                'operation': 'update',
                'body': {
                    'wan1': {
                        'usingStaticIp': True,
                        'vlan': vlan if '.2' in ip else None,  # no VLAN tag for AP
                        'staticIp': ip,
                        'staticGatewayIp': ip[:-1] + '1',  # strip last digit, and use MX which is .1
                        'staticSubnetMask': '255.255.255.0',
                        'staticDns': ['208.67.220.220', '208.67.222.222'],
                    }
                }
            }
            actions.append(action)


# Helper function configure MX VLANs
def batch_vlans(actions, net_id, num, mgmt_vlan):
    # Management VLAN
    if mgmt_vlan == 1:
        # Update default VLAN1
        actions.append({
            'resource': f'/networks/{net_id}/vlans/1',
            'operation': 'update',
            'body': {
                'id': mgmt_vlan,
                'name': f'Site {num} - Management',
                'subnet': f'10.{num}.1.0/24',
                'applianceIp': f'10.{num}.1.1'
            }
        })
    else:
        # Add new VLAN
        actions.append({
            'resource': f'/networks/{net_id}/vlans',
            'operation': 'create',
            'body': {
                'id': mgmt_vlan,
                'name': f'Site {num} - Management',
                'subnet': f'10.{num}.1.0/24',
                'applianceIp': f'10.{num}.1.1'
            }
        })
        # Delete VLAN1
        actions.append({
            'resource': f'/networks/{net_id}/vlans/1',
            'operation': 'delete',
            'body': {}
        })

    # Add more VLANs
    for (x, name) in zip(range(1, 4), ['Data', 'Voice', 'Guest']):
        vlan = str(num) + str(x)
        action = {
            'resource': f'/networks/{net_id}/vlans',
            'operation': 'create',
            'body': {
                'id': vlan,
                'name': f'Site {num} - {name}',
                'subnet': f'10.{num}.{vlan}.0/24',
                'applianceIp': f'10.{num}.{vlan}.1'
            }
        }
        actions.append(action)


# Helper function to configure group policies
def batch_policies(actions, net_id, teleworker):
    names = ['Executive', 'Guest', 'Sales']
    for name in names:
        if teleworker:
            body = policies_z[name]
        else:
            body = policies[name]
        body['name'] = name
        action = {
            'resource': f'/networks/{net_id}/groupPolicies',
            'operation': 'create',
            'body': body
        }
        actions.append(action)


# Helper function to configure MS switchports
def batch_switchports(actions, switch, num, vlan, custom_tags):
    if switch:
        for x in range(1, 10):
            body = {}
            if x == 1:
                body = {
                    'name': 'Uplink to MX',
                    'type': 'trunk',
                    'vlan': vlan,
                }
            elif x == 3:
                body = {
                    'name': 'MR wireless AP',
                    'type': 'trunk',
                    'vlan': vlan,
                }
            elif x == 5:
                body = {
                    'name': 'MV security camera',
                    'type': 'trunk',
                    'vlan': vlan,
                }
            elif x == 7:
                body = {
                    'name': 'ready to connect!',
                    'type': 'access',
                    'vlan': random.choice(range(vlan + 1, vlan + 4)),
                }
            elif x == 9:
                body = {
                    'name': 'SFP port',
                    'type': 'trunk',
                    'vlan': vlan,
                }
            else:
                continue
            body['tags'] = ' '.join(random.sample(custom_tags + ['foo', 'bar', 'foobar', 'spam', 'ham', 'eggs'], 3))
            action = {
                'resource': f'/devices/{switch}/switchPorts/{x}',
                'operation': 'update',
                'body': body
            }
            actions.append(action)


# Create/configure settings using action batches
def create_settings(api_key, org_id, actions, counter):
    counter += 1
    with open(f'create_settings_{counter}.json', 'w') as fp:
        payload = {
            'confirmed': True,
            'synchronous': True,
            'actions': actions
        }
        json.dump(payload, fp)

    print(f'POSTing one synchronous action batch to configure settings, payload in create_settings_{counter}.json')
    (ok, data) = create_action_batch(api_key, org_id, True, True, actions)
    if not ok:
        if len(data) < 10 ** 3:
            print(data)
    else:
        batch_id = data['id']
        if data['status']['completed']:
            print(f'Action batch {batch_id} completed!')
            return True
        elif data['status']['failed']:
            print(f'Action batch {batch_id} failed with errors {data["status"]["errors"]}!')
            return False


def main():
    # Read API key and org ID from local credentials.ini file
    try:
        cp = configparser.ConfigParser()
        cp.read('credentials.ini')
        api_key = cp.get('provisioning', 'key')
        org_id = cp.get('provisioning', 'org')
        token = cp.get('chatbot', 'token')
        email = cp.get('chatbot', 'email')
    # Ask user to input API key and check org access
    except:
        token = BOT_TOKEN
        email = USER_EMAIL
        while True:
            api_key = input('Enter your Meraki dashboard API key with full read/write org-wide access to an organization with API enabled: ')
            (ok, orgs) = get_user_orgs(api_key)
            if ok:
                break
            else:
                print('Please check that API key and try again!\n')

        # Get organization ID
        org_ids = []
        print('That API key has access to these organizations with names & IDs, respectively:')
        counter = 1
        for org in orgs:
            org_id = org["id"]
            org_ids.append(str(org_id))
            print(f'{counter:2}) {org["name"][:50]:50}\t{org_id:<18}')
            counter += 1
        print()
        while True:
            org_id = input('Enter the row # or org ID: ')
            try:
                if int(org_id) <= len(orgs):
                    org_id = org_ids[int(org_id) - 1]
            except:
                pass
            if org_id in org_ids:
                break
            else:
                print('That org ID is not one listed, try again!\n')
        print()

    # Store state in a file called demo_data.json
    try:
        with open('demo_data.json') as fp:
            demo_data = json.load(fp)
            demo_data['api_key'] = api_key
            demo_data['org_id'] = org_id
    except (FileNotFoundError, JSONDecodeError):
        demo_data = {'api_key': api_key, 'org_id': org_id}

    # Get name and custom tags
    if 'user_name' not in demo_data:
        user_name = input('Enter in your name(s): ')
        demo_data['user_name'] = user_name
    else:
        user_name = demo_data['user_name']
    if 'custom_tags' not in demo_data:
        custom_tags = input('Enter in some optional custom tag(s): ')
        custom_tags = custom_tags.split()
        demo_data['custom_tags'] = custom_tags
    else:
        custom_tags = demo_data['custom_tags']

    # Save state before making changes
    with open('demo_data.json', 'w') as fp:
        json.dump(demo_data, fp)
    print()

    # Create some stuff
    while True:
        print('1) Create your networks\n2) Add devices to them\n3) Configure many settings\n4) Have some fun!\n5) Reset & end this demo!')
        stop = input('What would you like to demo? ')
        stop = stop.lower()
        if 'network' in stop:
            stop = '1'
        elif 'device' in stop:
            stop = '2'
        elif 'setting' in stop:
            stop = '3'
        elif 'fun' in stop:
            stop = '4'
        elif 'reset' in stop or 'end' in stop:
            stop = '5'
        print()
        if stop not in ('1', '2', '3', '4', '5', '6'):
            continue

        with open('demo_data.json') as fp:
            demo_data = json.load(fp)

        if not os.path.exists('inventory.csv'):
            print('Local file "inventory.csv" not found, so please copy over to the same folder before proceeding.\n')
            continue

        # Creating networks
        if stop == '1':
            # Read input inventory.csv
            with open('inventory.csv', newline='\n', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
                sites = []
                locations = []
                time_zones = []
                for row in reader:
                    site = row['Site']
                    location = f'Demo {row["Location"].replace(",", " -")}'
                    time_zone = row['Time Zone']
                    sites.append(site)
                    locations.append(location)
                    time_zones.append(time_zone)

            # Create networks if not already done
            (ok, data) = get_networks(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                networks = data
            net_names = [net['name'] for net in networks]
            if set(net_names).intersection(set(locations)):
                print('Networks already created!')
                continue
            else:
                create_networks(api_key, org_id, sites, locations, custom_tags, time_zones)

            # Update demo_data.json
            demo_data['networks'] = []
            (ok, data) = get_networks(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                networks = data
            net_names = [network['name'] for network in networks]
            for (site, location) in zip(sites, locations):
                if location in net_names:
                    net_id = networks[net_names.index(location)]['id']
                    demo_data['networks'].append({'net_id': net_id, 'location': location, 'site': site})
            with open('demo_data.json', 'w') as fp:
                json.dump(demo_data, fp)
            print('Log file demo_data.json updated\n')

        # Adding devices
        elif stop == '2':
            # Check networks already created
            (ok, data) = get_networks(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                networks = data
            if not networks or 'networks' not in demo_data or not demo_data['networks']:
                print('Networks need to be created first!')
                continue
            elif 'devices' in demo_data['networks'][0] and demo_data['networks'][0]['devices']:
                print('Devices already added!')
                continue

            # Proceed to claim devices
            with open('inventory.csv', newline='\n', encoding='utf-8-sig') as csvfile:
                counter = 0
                actions = []
                reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
                for row in reader:
                    net_id = demo_data['networks'][counter]['net_id']
                    mx_serial = row['MX device']
                    ms_serial = row['MS device']
                    mr_serial = row['MR device']
                    mv_serial = row['MV device']
                    mgmt_vlan = int(row['Mgmt. VLAN'])
                    for serial in (mx_serial, ms_serial, mr_serial, mv_serial):
                        add_devices(actions, net_id, serial)
                    devices = [[mx_serial, 'SD-WAN UTM gateway'],
                               [ms_serial, 'Access switch'],
                               [mr_serial, 'Wireless AP'],
                               [mv_serial, 'Security camera']]
                    demo_data['networks'][counter]['devices'] = devices
                    demo_data['networks'][counter]['mgmt_vlan'] = mgmt_vlan
                    counter += 1

                create_devices(api_key, org_id, actions)

                # Check for Z-teleworker devices
                (ok, inv) = get_inventory(api_key, org_id)
                if ok:
                    teleworkers = [d for d in inv if d['model'][:2] in ('Z1', 'Z3')]
                    z_serials = [d['serial'] for d in teleworkers]
                    for network in demo_data['networks']:
                        for [serial, desc] in network['devices']:
                            if serial in z_serials:
                                network['devices'][0][1] = 'Teleworker gateway'

            # Update demo_data.json
            with open('demo_data.json', 'w') as fp:
                json.dump(demo_data, fp)
            print('Log file demo_data.json updated\n')

        # Configuring settings
        elif stop == '3':
            # Check networks already created and devices already added
            (ok, data) = get_networks(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                networks = data
            if not networks or 'networks' not in demo_data or not demo_data['networks']:
                print('Networks need to be created first!')
                continue
            elif 'devices' not in demo_data['networks'][0]:
                print('Devices need to be added first!')
                continue

            # Get inventory to determine the model of MX for port configuration
            (ok, inv) = get_inventory(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                inventory = {d['serial']: d['model'] for d in inv if d['networkId']}

            with open('inventory.csv', newline='\n', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
                counter = 0
                for row in reader:
                    actions = []
                    net_id = demo_data['networks'][counter]['net_id']
                    mx_serial = row['MX device']
                    ms_serial = row['MS device']
                    mr_serial = row['MR device']
                    mgmt_vlan = int(row['Mgmt. VLAN'])
                    site = demo_data['networks'][counter]['site']
                    location = demo_data['networks'][counter]['location']
                    address = row['Address'] if 'Address' in row else location.replace('Demo ', '')
                    devices = demo_data['networks'][counter]['devices']
                    teleworker = False
                    for (device, description) in devices:
                        configure_device(actions, net_id, device, description, address, user_name, custom_tags)
                        if description == 'Teleworker gateway':
                            teleworker = True

                    # Configure SSID
                    open_ssid(api_key, net_id, 0, 'Code🐵get⬆get☕')

                    # Configure management IP addresses (uplink interfaces) via action batch
                    batch_devices(actions, net_id, [(ms_serial, row['MS IP']), (mr_serial, row['MR IP'])], mgmt_vlan)

                    # Cannot re-create VLANs or group policies if already done
                    settings_created = ('settings_created' in demo_data['networks'][counter] and
                                        demo_data['networks'][counter]['settings_created'])
                    if not settings_created:
                        batch_vlans(actions, net_id, site, mgmt_vlan)  # create VLANs
                        batch_policies(actions, net_id, teleworker)  # create group policies

                    # Batch MX port
                    if mx_serial:
                        model = inventory[mx_serial]
                        if 'Z3' in model or 'MX67' in model or model == 'MX100':
                            batch_mx_port(actions, net_id, mgmt_vlan, 5)    # Z3's port 5 provides PoE
                        else:
                            batch_mx_port(actions, net_id, mgmt_vlan, 12)   # MX68/MX65's port 12 provides PoE

                    # Batch MS ports
                    batch_switchports(actions, ms_serial, site, mgmt_vlan, custom_tags)  # configure switch ports

                    # Check and update status
                    done = create_settings(api_key, org_id, actions, counter)
                    demo_data['networks'][counter]['settings_created'] = done
                    counter += 1

            # Update demo_data.json
            with open('demo_data.json', 'w') as fp:
                json.dump(demo_data, fp)
            print('Log file demo_data.json updated\n')

        # Creating fun!
        elif stop == '4':
            # Check networks already created and devices already added
            (ok, data) = get_networks(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                networks = data
            if not networks or 'networks' not in demo_data or not demo_data['networks']:
                print('Networks need to be created first!')
                continue
            elif 'devices' not in demo_data['networks'][0]:
                print('Devices need to be claimed first!')
                continue
            else:
                print('Looking for online devices...')

            # Check devices are online
            (ok, data) = get_device_statuses(api_key, org_id)
            if not ok:
                sys.exit(data)
            else:
                statuses = {d['serial']: d['status'] for d in data}
            stage_net = demo_data['networks'][0]['net_id']
            stage_devices = demo_data['networks'][0]['devices']
            stage_cam = demo_data['networks'][0]['devices'][3][0]

            # Blink LEDs
            for (device, description) in stage_devices:
                if device and statuses[device] != 'offline':
                    (ok, data) = blink_device(api_key, stage_net, device, 120)
                    if ok:
                        print(f'{description} blinking!')

            # Take a snapshot from on-stage camera, while waiting for camera to come online
            attempts = 6
            while attempts > 0:
                time.sleep(6)
                (ok, data) = get_device_statuses(api_key, org_id)
                if not ok:
                    sys.exit(data)
                else:
                    statuses = {d['serial']: d['status'] for d in data}
                if statuses[stage_cam] != 'offline':
                    for x in range(1, 4):
                        if x == 1:
                            message = '## 🎉🥂 Thank you for attending _[Adventure API Lab 2.0](http://cs.co/adventure2)_! 💪📝'
                        elif x == 2:
                            message = '## ✅😇 Check out the Developer Hub @ meraki.io! 🌎💚'
                        elif x == 3:
                            message = '## 🌟💫 Hope you enjoyed this lab, and thanks for watching! 🤜🤛'

                        (ok, data) = take_snapshot(api_key, stage_net, stage_cam)
                        if ok:
                            file = try_snapshot(data['url'], f'demo{x}')
                            if file:
                                send_file(message, file, 'image/jpg', token, email)
                    break
                else:
                    attempts -= 1

        # Bye!
        elif stop == '5':
            if 'networks' in demo_data and demo_data['networks']:
                for net in demo_data['networks']:
                    ok = delete_network(api_key, net['net_id'])
                    if ok:
                        net_name = net['location']
                        print(f'Network {net_name} deleted!')
            demo_files = ['demo_data.json', 'create_devices.json', 'create_networks.json']
            demo_files.extend(glob.glob('create_settings_*.json'))
            demo_files.extend(glob.glob('demo*.jpg'))
            for file in demo_files:
                if os.path.exists(file):
                    os.remove(file)
            sys.exit('Take care!')


if __name__ == '__main__':
    main()
