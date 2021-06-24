import uuid
import websocket
import json
import os
import logging
import time
from threading import Thread

from ...core.reporting.callbacks import *

SLACK_WEBSOCKET_RELAY_ADDRESS = os.environ.get('SLACK_WEBSOCKET_RELAY_ADDRESS', "")
SLACK_RECEIVER_ENABLED = os.environ.get('SLACK_RECEIVER_ENABLED', "True")
SLACK_ENABLE_WEBSOCKET_TRACING = os.environ.get('SLACK_ENABLE_WEBSOCKET_TRACING', False)
SLACK_WEBSOCKET_RECONNECT_DELAY_SEC = os.environ.get('SLACK_WEBSOCKET_RECONNECT_DELAY_SEC', 3)
TARGET_ID = str(uuid.uuid4())


def run_report_callback(action, body):
    callback_request = PlaybookCallbackRequest.parse_raw(action['value'])
    func = callback_registry.lookup_callback(callback_request)
    event = ReportCallbackEvent(source_channel_id=body['channel']['id'],
                                source_channel_name=body['channel']['name'],
                                source_user_id=body['user']['id'],
                                source_message=body['message']['text'],
                                source_context=callback_request.context)
    logging.info(f"got callback `{func}`")
    if func is None:
        logging.error(f"no callback found for action_id={action['action_id']} with value={action['value']}")
        return
    func(event)


def start_slack_receiver():
    if SLACK_RECEIVER_ENABLED != "True":
        logging.info("Slack outgoing messages only mode. Slack receiver not initialized")
        return

    if SLACK_WEBSOCKET_RELAY_ADDRESS == "":
        logging.warning("Slack relay adress empty. Not initializing slack relay")
        return

    websocket.enableTrace(SLACK_ENABLE_WEBSOCKET_TRACING)
    receiver_thread = Thread(target=run_forever)
    receiver_thread.start()


def run_forever():
    logging.info('starting slack relay receiver')
    while True:
        ws = websocket.WebSocketApp(SLACK_WEBSOCKET_RELAY_ADDRESS,
                                    on_open=on_open,
                                    on_message=on_message,
                                    on_error=on_error)
        ws.run_forever()
        logging.info('slack relay websocket closed')
        time.sleep(SLACK_WEBSOCKET_RECONNECT_DELAY_SEC)


def on_message(ws, message):
    # TODO: use typed pydantic classes here?
    logging.debug(f'received slack message {message}')
    slack_event = json.loads(message)
    actions = slack_event['actions']
    for action in actions:
        run_report_callback(action, slack_event)


def on_error(ws, error):
    logging.info(f'slack relay websocket error: {error}')

def on_open(ws):
    logging.info(f'connecting to server as {TARGET_ID}')
    ws.send(json.dumps({'action': 'auth', 'key': 'dummy key', 'target_id': TARGET_ID}))


