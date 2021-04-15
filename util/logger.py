import logging
import warnings

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.DEBUG)
warnings.filterwarnings('ignore', category=DeprecationWarning)

DEBUG = 0


def print_listener_configs(listener_configs):
    """
    Print the initialized @ListenerConfig objects
    :param listener_configs: the initialized @ListenerConfig objects
    :return: /
    """
    for config in listener_configs:
        print(config)


def print_listeners(listeners):
    """
    Print the initialized @Listener or @TLSListener objects
    :param listeners: the initalized listeners
    :return: /
    """
    for listener in listeners:
        print(listener)


def log_multilateral(listener, client, message, sub, payload, topic, publisher_id, subscriber_id, entity='sub'):
    """
    Logs detailed information on why the publish message was not forwarded. Caused by the multilateral security
    setting, but can have many different reasons.
    :param listener: 1 if listener enforces multilateral security, else 0
    :param client: 1 if publisher enforces multilateral security (in CONNECT), else 0
    :param message: 1 if publisher enforced multilateral security per message (in PUBLISH), else 0
    :param sub: 1 if the subscriber enforced multilateral security, else 0
    :param payload: payload of the publish message
    :param topic: topic of the publish message
    :param publisher_id: client_id of the publisher
    :param subscriber_id: client_id of the subscriber
    :param entity: "pub" if publisher is the reason for not forwarding, "sub" if the subscriber.
    """
    entity = 'Publisher' if entity == 'pub' else 'Subscriber'
    client_type = 'TLS' if entity == 'Publisher' else 'non-TLS'
    multilateral_security_reason = "as multilateral security is enforced by the "
    if listener:
        multilateral_security_reason += "broker-listener."
    elif client:
        multilateral_security_reason += "publisher."
    elif message:
        multilateral_security_reason += "publisher for this message."
    elif sub:
        multilateral_security_reason += "subscriber."
    client_id = publisher_id if entity == 'Publisher' else subscriber_id
    multilateral_security_effect = f"{entity} {client_id} must use a secure communication channel."
    logging.info(f"Did not forward '{topic}:{payload}' to {client_type} Client {subscriber_id} {multilateral_security_reason} {multilateral_security_effect}")