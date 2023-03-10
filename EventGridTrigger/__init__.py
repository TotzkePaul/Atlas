import json
import logging
import os

import azure.functions as func
from azure.communication.sms import SmsClient
from azure.identity import DefaultAzureCredential

import openai 

def main(event: func.EventGridEvent):
    try:
        respond(event)
    except Exception as e:
        logging.error('Error at %s', 'respond', exc_info=e)

def remember(message: str):
    messages = []

    messages.append({"role": "system", "content" : "You are a friend."})
    messages.append({"role": "assistant", "content" : "I want to understand you better."})
    messages.append({"role": "user", "content" : message})
    return messages

def think(input_text: str):
    logging.info('Python OpenAI is thinking about: %s', input_text)
    openai.api_key = os.environ["OPENAI_API_KEY"]

    message_log = remember(input_text)
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=message_log,   
        max_tokens=50,         
        stop=None,              
        temperature=0.7,
    )
    
    for choice in response.choices:
        if "text" in choice:
            return choice.text

    # If no response with text is found, return the first response's content (which may be empty)
    return response.choices[0].message.content

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

    reply_message = think( event_json['message'])

    logging.info('Python EventGrid trigger preparing an sms response: From: %s, To: %s, Message: %s', 
                 from_phone_number, to_phone_number, reply_message)

    sms_responses = sms_client.send(
        from_=from_phone_number,
        to= to_phone_number,
        message=reply_message,
        enable_delivery_report=True, # optional property
        tag="beta-test") # optional property
    
    logging.info('Python EventGrid trigger processed an sms response: %s', sms_responses.get_json())
