import json
import random
import re

from chatbot import *
from status import *


# Display input card with form for creating network and claiming devices
def get_inputs(session, headers, payload, api_key, org_id):
    # Load cards for Webex Teams
    with open('deploy.json') as fp:
        card = json.load(fp)
    card['roomId'] = payload['roomId']

    # Get org inventory, and list up to 7 serials of each product family
    inventory = get_org_inventory(session, api_key, org_id)
    unused = [d for d in inventory if not d['networkId']]
    random.shuffle(unused)
    mx_unused = [d for d in unused if d['model'][:2] in ('MX', 'Z1', 'Z3')][:7]
    mx_unused = sorted(mx_unused, key=lambda d: d['model'], reverse=True)
    ms_unused = [d for d in unused if d['model'][:2] == 'MS'][:7]
    ms_unused = sorted(ms_unused, key=lambda d: d['model'], reverse=True)
    mr_unused = [d for d in unused if d['model'][:2] == 'MR'][:7]
    mr_unused = sorted(mr_unused, key=lambda d: d['model'], reverse=True)
    mv_unused = [d for d in unused if d['model'][:2] == 'MV'][:7]
    mv_unused = sorted(mv_unused, key=lambda d: d['model'], reverse=True)

    # Format output of card
    new_card_items = []
    for (product, unused) in zip(('MX', 'MS', 'MR', 'MV'), (mx_unused, ms_unused, mr_unused, mv_unused)):
        new_card_items.append({'type': 'TextBlock', 'text': f'{product} serial number'})
        choices = []
        for d in unused:
            choices.insert(0, {'title': f'{d["serial"]} ({d["model"]})', 'value': d['serial']})
        if choices:
            new_card_items.append({'type': 'Input.ChoiceSet', 'id': f'{product}SelectVal', 'style': 'compact',
                                   'value': d['serial'], 'choices': choices})
        else:
            new_card_items.append({'type': 'Input.ChoiceSet', 'id': f'{product}SelectVal', 'style': 'compact',
                                   'value': 'none', 'choices': [{'title': '(none available)', 'value': 'none'}]})

    card['attachments'][0]['content']['body'][0]['columns'][0]['items'].extend(new_card_items)
    session.post('https://api.ciscospark.com/v1/messages', headers=headers, json=card)


# Display error card
def display_error(session, headers, payload, message):
    # Load cards for Webex Teams
    with open('error.json') as fp:
        card = json.load(fp)
    card['roomId'] = payload['roomId']
    card['attachments'][0]['content']['body'][0]['columns'][0]['items'][2]['text'] = message
    session.post('https://api.ciscospark.com/v1/messages', headers=headers, json=card)


# Display success card
def display_success(session, headers, payload, name, devices):
    # Load cards for Webex Teams
    with open('success.json') as fp:
        card = json.load(fp)
    card['roomId'] = payload['roomId']
    card['attachments'][0]['content']['body'][0]['columns'][0]['items'][2]['text'] = f'Network **{name}** created with **{devices}** devices deployed!'
    session.post('https://api.ciscospark.com/v1/messages', headers=headers, json=card)


# Process inputs based on form or confirmation card
def process_inputs(session, headers, payload, api_key, org_id, inputs):
    # Empty submission (try again)
    inputs = inputs['inputs']
    if not inputs:
        return get_inputs(session, headers, payload, api_key, org_id)

    # Check location/name of network for user errors
    if 'myLocation' in inputs and not inputs['myLocation']:
        return display_error(session, headers, payload, 'You need to specify a location for the network name!')
    elif 'myLocation' in inputs:
        name = 'Demo ' + inputs['myLocation'].replace(',', ' -')
        name = ''.join([c for c in name if c.isalnum() or c in '.@#_- '])
        networks = get_networks(session, api_key, org_id)
        if name in [n['name'] for n in networks]:
            return display_error(session, headers, payload, 'That location/name is already used by an existing network!')

    # Check inventory
    inventory = get_org_inventory(session, api_key, org_id)
    unused = [d['serial'] for d in inventory if not d['networkId']]
    to_add = [inputs['MXSelectVal'], inputs['MSSelectVal'], inputs['MRSelectVal'], inputs['MVSelectVal']]
    to_add = [serial for serial in to_add if serial != 'none']

    # Check serials are still available to be claimed
    if len(to_add) == 0 or len(set(unused).intersection(to_add)) == 0:
        return display_error(session, headers, payload, 'Please select serial numbers that are available in inventory!')
    else:
        post_message(session, headers, payload, 'One moment please...')
        if inputs['myAddress']:
            address = f'{inputs["myAddress"]}, {inputs["myLocation"]}'
        network = create_network(session, api_key, org_id, name=name, type='appliance switch wireless camera')
        devices = 0
        for serial in to_add:
            added = claim_device(session, api_key, network['id'], serial)
            if added:
                devices += 1
                update_device(session, api_key, network['id'], serial, name='Device', address=address, moveMapMarker=True)
        return display_success(session, headers, payload, name, devices)
