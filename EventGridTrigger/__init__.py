import json
import logging
import os

import azure.functions as func
from azure.communication.sms import SmsClient
from azure.identity import DefaultAzureCredential


def main(event: func.EventGridEvent):

    try:
        respond(event)
    except Exception as e:
        logging.error('Python EventGrid Error', e)


def respond(event: func.EventGridEvent):
    event_json = event.get_json()

    result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })

    logging.info('Python EventGrid trigger processed an event: %s', result)

    endpoint = 'https://atlassms.communication.azure.com/'
    accesskey = os.environ["SMS_ACCESS_KEY"]

    connection_str = f'endpoint={endpoint};accesskey={accesskey}'
        
    sms_client = SmsClient.from_connection_string(connection_str)

    from_phone_number = event_json['to']
    to_phone_number = event_json['from']

    reply_message = 'ECHO: ' + event_json['message']

    logging.info('Python EventGrid trigger preparing an sms response: From: %s, To: %s, Message: %s', 
                 from_phone_number, to_phone_number, reply_message)

    sms_responses = sms_client.send(
        from_=from_phone_number,
        to= to_phone_number,
        message=reply_message,
        enable_delivery_report=True, # optional property
        tag="beta-test") # optional property
    
    logging.info('Python EventGrid trigger processed an sms response: %s', sms_responses.get_json())
