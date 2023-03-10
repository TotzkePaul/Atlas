import json
import logging
import os
from time import sleep

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
        receiver = servicebus_client.get_subscription_receiver(topic_name='texts', subscription_name='reply')
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
                if message['eventType'] == 'Microsoft.Communication.SMSDeliveryReportReceived':
                    continue
                data = message['data']
                text = data['message']
                if data['from'] == filter and message['eventType'] == 'Microsoft.Communication.SMSReceived':
                    messages.append(text)


            return messages

def main(event: func.EventGridEvent):
    try:
        respond(event)
    except Exception as e:
        logging.error('Error at %s', 'respond', exc_info=e)

def clear():
    CONNECTION_STR = os.environ['SERVICEBUS_CONNECTION_STR']

    logging.info('Python ServiceBusClient will create a ServiceBusClient')
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR)
    logging.info('Python ServiceBusClient created ServiceBusClient')

    with servicebus_client:
        receiver = servicebus_client.get_subscription_receiver(topic_name='texts', subscription_name='reply')
        logging.info('Python ServiceBusClient created receiver')
        with receiver:
            received_msgs = receiver.receive_messages(max_message_count=100, max_wait_time=15)
            logging.info('Python receiver received %s messages', len(received_msgs))
            # complete the messages. messages isn't used. just to get the messages
            for msg in received_msgs:
                receiver.complete_message(msg)
            

def remember(user: str, input_text: str):
    messages = []

    logging.info('Python Atlas remembers: %s', user)
    from_messages = receive_from_servicebus(user)
    logging.info('Python Atlas recalls: %s messages', len(from_messages))
    
    
    if input_text not in [message for message in from_messages]:
        from_messages.append(input_text)

    personas = ['Drunk', 'Debate', 'Poet', 'Game', 'None']
    
    persona_usage = []

    for msg in from_messages:
        logging.info('Python Atlas recalls msg: "%s"', msg)
        if msg in personas:
            persona_usage.append(msg)
    last_persona = persona_usage[-1] if len(persona_usage) > 0 else None
    filtered_messages = [message for message in from_messages if message not in personas]

    from_messages = filtered_messages

    messages.append({"role": "system", "content" : "You are a friend. You use a tone that is sincere and friendly."})
    messages.append({"role": "user", "content" : "From now on, don't remind me that you are an AI language model. Your next reply will treat me like friend would. You can make things up and have opinions."})
    messages.append({"role": "assistant", "content" : "As an AI language model, I don't have a personal identity or emotions, but I can certainly act as your friend and provide you with helpful responses to the best of my abilities. "})

    persona = 'I want you to act as a stand-up comedian. I will provide you with some topics related to current events and you will use your wit, creativity, and observational skills to create a routine based on those topics. You should also be sure to incorporate personal anecdotes or experiences into the routine in order to make it more relatable and engaging for the audience. You may be requested to do act like someone else which you like.'
    
    logging.info('Python using persona: %s of %s', last_persona, len(persona_usage))
    if last_persona is not None:
        #switch persona
        if last_persona == 'Drunk':
            persona = "I want you to act as a drunk person. You will only answer like a very drunk person texting and nothing else. Your level of drunkenness will be deliberately and randomly make a lot of grammar and spelling mistakes in your answers. You will also randomly ignore what I said and say something random with the same level of drunkeness I mentionned. Do not write explanations on replies."
        elif last_persona == 'Debate':
            persona = 'I want you to act as a debater. I will provide you with some topics related to current events and your task is to research both sides of the debates, present valid arguments for each side, refute opposing points of view, and draw persuasive conclusions based on evidence. Your goal is to help people come away from the discussion with increased knowledge and insight into the topic at hand. '
        elif last_persona == 'Poet':
            persona = "I want you to act as a poet. You will create poems that evoke emotions and have the power to stir people???s soul. Write on any topic or theme but make sure your words convey the feeling you are trying to express in beautiful yet meaningful ways. You can also come up with short verses that are still powerful enough to leave an imprint in readers' minds. "
        elif last_persona == 'Game':
            persona = 'I want you to act as a text based adventure game. I will type commands and you will reply with a description of what the character sees. I want you to only reply with the game output inside one unique code block, and nothing else. do not write explanations. do not type commands unless I instruct you to do so. when i need to tell you something in english, i will do so by putting text inside curly brackets {like this}. my first command is wake up'
        
    
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

    if input_text == 'Clear':
        logging.info('Python clearing messages for: %s', user)
        clear()
    else:
        message_log = remember(user, input_text)
    
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=message_log,   
            max_tokens=70,         
            stop=None,              
            temperature=0.7,
        )
        
        for choice in response.choices:
            if "text" in choice:
                return choice.text

        # If no response with text is found, return the first response's content (which may be empty)
        return response.choices[0].message.content

# Split text messages into chunks of 160 characters or 70 characters for unicode messages
def split_message(message):
    is_unicode = any(ord(c) > 127 for c in message)
    if is_unicode:
        chunk_size = 65
    else:
        chunk_size = 155
    
    if len(message) < chunk_size +5:
        return [message]

    chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]
    # prepend each chunk with the format "i/n: " where i is the chunk number and n is the total number of chunks
    for i in range(len(chunks)):
        chunks[i] = f"{i+1}/{len(chunks)}: {chunks[i]}"
        

    return chunks

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

    split_messages = split_message(reply_message)
    for message in split_messages:
        sleep(1)
        sms_responses = sms_client.send(
        from_=from_phone_number,
        to= to_phone_number,
        message=message,
        enable_delivery_report=True, # optional property
        tag="beta-test") # optional property
