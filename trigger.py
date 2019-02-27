from meraki import meraki

from chatbot import *


# Disable port's PoE to trigger webhook alert
def disable_port(session, headers, payload, api_key, net_id):
    switch_serial = 'Q2**-****-****'
    response = meraki.getswitchportdetail(api_key, switch_serial, 5)
    if not response['enabled']:
        post_message(session, headers, payload, 'Port already disabled!')
    else:
        response = meraki.updateswitchport(api_key, switch_serial, 5, enabled=False)
        if response['enabled']:
            post_message(session, headers, payload, 'Something went wrong!')
        else:
            post_message(session, headers, payload, 'Disabled your switchport!')


# Enable port's PoE to undo above (and trigger another webhook)
def enable_port(session, headers, payload, api_key, net_id):
    switch_serial = 'Q2**-****-****'
    response = meraki.getswitchportdetail(api_key, switch_serial, 5)
    if response['enabled']:
        post_message(session, headers, payload, 'Port already enabled!')
    else:
        response = meraki.updateswitchport(api_key, switch_serial, 5, enabled=True)
        if response['enabled']:
            post_message(session, headers, payload, 'Enabled your switchport!')
        else:
            post_message(session, headers, payload, 'Something went wrong!')
