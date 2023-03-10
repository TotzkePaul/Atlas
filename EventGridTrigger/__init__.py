import json
import logging
import os

import azure.functions as func
from azure.communication.sms import SmsClient
from azure.identity import DefaultAzureCredential

import openai 

from azure.servicebus import ServiceBusClient


def receive_from_servicebus(filter: str):
    CONNECTION_STR = os.environ['SERVICEBUS_CONNECTION_STR']

    logging.info('Python ServiceBusClient will create a ServiceBusClient')
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR)
    logging.info('Python ServiceBusClient created ServiceBusClient')

    with servicebus_client:
        receiver = servicebus_client.get_subscription_receiver(topic_name='texts', subscription_name='texts')
        logging.info('Python ServiceBusClient created receiver')
        with receiver:
            received_msgs = receiver.receive_messages(max_message_count=100, max_wait_time=15)
            logging.info('Python receiver received %s messages', len(received_msgs))
            
            messages = []
            for msg in received_msgs:
                my_body = list(msg.body)[0]

                my_body = my_body.decode('utf-8') if isinstance(my_body, bytes) else my_body
                logging.info('Python ServiceBusClient has body: %s', my_body)
                
                #logging.info('Python ServiceBusClient has decoded body: %s', my_body)
                message = json.loads(my_body)
                logging.info('Python ServiceBusClient has message: %s', message)
                data = message['data']
                text = data['message']
                if data['to'] == filter and message['event_type'] == 'Microsoft.Communication.SMSReceived':
                    messages.append(text)


            return messages

def main(event: func.EventGridEvent):
    try:
        respond(event)
    except Exception as e:
        logging.error('Error at %s', 'respond', exc_info=e)

def remember(user: str, input_text: str):
    messages = []

    logging.info('Python Atlas remembers: %s', user)
    from_messages = receive_from_servicebus(user)
    logging.info('Python Atlas recalls: %s messages', len(from_messages))
    

    messages.append({"role": "system", "content" : "You are a friend. You use a tone that is sincere and friendly."})
    messages.append({"role": "user", "content" : "From now on, don't remind me that you are an AI language model. Your next reply will treat me like friend would. You can make things up and have opinions."})
    messages.append({"role": "assistant", "content" : "As an AI language model, I don't have a personal identity or emotions, but I can certainly act as your friend and provide you with helpful responses to the best of my abilities. "})
    
    persona = "I want you to act as a drunk person. You will only answer like a very drunk person texting and nothing else. Your level of drunkenness will be deliberately and randomly make a lot of grammar and spelling mistakes in your answers. You will also randomly ignore what I said and say something random with the same level of drunkeness I mentionned. Do not write explanations on replies."
    messages.append({"role": "assistant", "content" : persona})

    for message in from_messages:
        messages.append({"role": "user", "content" : message})
    
    # if input_text is not in the list of messages, add it
    if input_text not in [message for message in messages]:
        messages.append({"role": "user", "content" : input_text})
    return messages

def think(input_text: str, user: str):
    logging.info('Python OpenAI is thinking about: %s', input_text)
    openai.api_key = os.environ["OPENAI_API_KEY"]

    message_log = remember(user, input_text)
    
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

    reply_message = think( event_json['message'], to_phone_number)

    logging.info('Python EventGrid trigger preparing an sms response: From: %s, To: %s, Message: %s', 
                 from_phone_number, to_phone_number, reply_message)

    sms_responses = sms_client.send(
        from_=from_phone_number,
        to= to_phone_number,
        message=reply_message,
        enable_delivery_report=True, # optional property
        tag="beta-test") # optional property
    
    logging.info('Python EventGrid trigger processed an sms error: %s', sms_responses.error_message)
