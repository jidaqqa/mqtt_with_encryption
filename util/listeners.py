import socket
import threading
import ssl
from util.mqtt_packet_manager import MQTTPacketManager
import util.logger as logger
from util.exceptions import MQTTMessageNotSupportedException
from util.exceptions import IncorrectProtocolOrderException
from util.client_manager import *
import util.enums as enums

ALLOWED_CONNECTIONS = 10


class ClientThread(threading.Thread):
    """
    Handles the TCP sockets with the clients
    """
    def __init__(self, client_socket, client_address, listener, subscription_manager, client_manager, multilateral, debug, tls=0):
        super().__init__()
        self.client_socket = client_socket
        self.client_address = client_address
        self._running = True
        self._stop_event = threading.Event()
        self.listener = listener
        self._tls = tls
        self._subscription_manager = subscription_manager
        self._client_manager = client_manager
        self._multilateral = multilateral
        self.debug = debug
        self.client_id = ''

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self,value):
        self._running = value

    def run(self):
        """
        Start method of the thread
        """
        self.listen()

    def handle_connect(self, parsed_msg):
        """
        Handle the MQTT CONNECT message: update the status of the client to CONN_RECV, store the sent user properties
        in the ClientManager and set the ClientID. Afterwards send a CONNACK msg back to the client.
        :param parsed_msg: a parsed version of the received message
        """
        try:
            self._client_manager.add_status(self.client_socket, self.client_address, enums.Status.CONN_RECV)
            self._client_manager.add_user_property(self.client_socket, self.client_address, parsed_msg['properties'])
            self._client_manager.add_user_property(self.client_socket, self.client_address, {enums.Properties.Version: parsed_msg['version']})
            self.client_id = parsed_msg['client_id']
        except (IncorrectProtocolOrderException, TypeError) as e:
            logger.logging.error(e)
            self.close()
        connack_msg = MQTTPacketManager.prepare_connack(parsed_msg)
        self.client_socket.send(connack_msg)
        logger.logging.info(f"Sent CONNACK to client {parsed_msg['client_id']}.")

    def handle_publish(self, parsed_msg):
        """
        Handle the MQTT PUBLISH message: check if the client has a valid status (CONN_RECV or PUB_RECV), then update the
        client status to PUB_RECV. Also determine the multilateral security setting of the publisher (either multilateral
        security was set when connecting, then it will be applied on all publications or publisher defines the multilateral
        security setting per message, then it will only be applied for one specific message). Afterwards init the
        publication process: Based on the settings, one of three publishing scenarios can happen:
        1) Publisher connected via TLS and Broker or Publisher demands TLS: then only publish to TLS connected subscribers
        2) Publisher connected via non-TLS and Subscriber demands TLS: then subscriber won't receive the msg
        3) Else: every subscriber receives the msg
        :param parsed_msg: a parsed version of the received message
        """
        if self._client_manager.get_client_status(self.client_socket, self.client_address) in [enums.Status.CONN_RECV, enums.Status.PUB_RECV]:
            self._client_manager.add_status(self.client_socket, self.client_address, enums.Status.PUB_RECV)
            topic = parsed_msg['topic']
            message_multilateral = self._determine_message_multilateral(parsed_msg)
            client_multilateral = self._determine_client_multilateral()
            for sub in self._subscription_manager.get_topic_subscribers(topic):
                # if received on TLS listener then check for multilateral security. Subscriber must be TLS as well
                if self._tls and (self._multilateral or client_multilateral or message_multilateral):
                    if sub['tls']:
                        logger.logging.info(f"Sent TLS-Enforced publish message '{parsed_msg['payload']}' in '{topic}' to Client {sub['client_id']}")
                        sub['client_socket'].send(parsed_msg['raw_packet'])
                    else:
                        logger.log_multilateral(self._multilateral, client_multilateral, message_multilateral, sub['multilateral'], parsed_msg['payload'], topic, self.client_id, sub['client_id'], 'sub')
                # if received on Non-TLS Listener then check for multilateral and TLS of subscribers before sending. They should not receive it.
                elif not self._tls and sub['multilateral']:
                    if not sub['tls']:
                        logger.logging.info(f"Sent publish message '{parsed_msg['payload']}' in '{topic}' to Client {sub['client_id']}")
                        sub["client_socket"].send(parsed_msg['raw_packet'])
                    else:
                        logger.log_multilateral(self._multilateral, client_multilateral, message_multilateral, sub['multilateral'], parsed_msg['payload'], topic, self.client_id, sub['client_id'], 'pub')
                # just send to everybody
                else:
                    logger.logging.info(f"Sent publish message '{parsed_msg['payload']}' in '{topic}' to Client {sub['client_id']}")
                    sub["client_socket"].send(parsed_msg['raw_packet'])
        else:
            raise IncorrectProtocolOrderException(f"Received PUBLISH message from client {self.client_address} before CONNECT. Abort!")

    def handle_subscribe(self, parsed_msg):
        """
        Handle the MQTT SUBSCRIBE message: check if the client has a valid status (CONN_RECV or SUB_RECV), then update the
        client status to SUB_RECV. Add the client to the subscriber list and send a PUBACK message back to the client.
        :param parsed_msg: a parsed version of the received message
        """
        if self._client_manager.get_client_status(self.client_socket, self.client_address) in [enums.Status.CONN_RECV, enums.Status.SUB_RECV]:
            self._client_manager.add_status(self.client_socket, self.client_address, enums.Status.SUB_RECV)
            topic = parsed_msg['topic']
            client_multilateral = self._determine_client_multilateral()
            topic_multilateral = self._determine_message_multilateral(parsed_msg)
            self._subscription_manager.add_subscriber(self.client_socket, self.client_address, topic, self._tls,
                                                      (self._multilateral or client_multilateral or topic_multilateral), self.client_id)
            logger.logging.info(
                f"- Client {self.client_id} subscribed successfully to topic: '{topic}' on port {self.listener.port}")

            suback_msg = MQTTPacketManager.prepare_suback(parsed_msg)
            self.client_socket.send(suback_msg)
            logger.logging.info(f"Sent SUBACK to client {self.client_id}")
        else:
            raise IncorrectProtocolOrderException(
                f"Received SUBSCRIBE message from client {self.client_id} before CONNECT. Abort!")

    def handle_pingreq(self, parsed_msg):
        """
        Handle the MQTT PINGREQ message: Send a PINGRESP back to the client.
        :param parsed_msg: a parsed version of the received message (FOR FUTURE USE)
        :return:
        """
        pingresp_msg = MQTTPacketManager.prepare_pingresp()
        self.client_socket.send(pingresp_msg)
        logger.logging.info(f"Sent PINGRESP to client {self.client_address}.")

    def handle_disconnect(self, parsed_msg):
        """
        Handle the MQTT DISCONNECT message: update the status of the client to DISCONNECTED and remove the client
        , if necessary, from the all subscription lists. Finally close the responsible client thread.
        :param parsed_msg: a parsed version of the received message (FOR FUTURE USE)
        """
        self._client_manager.add_status(self.client_socket, self.client_address, enums.Status.DISCONNECTED)
        client_multilateral = self._determine_client_multilateral()
        self._subscription_manager.remove_subscriber(self.client_socket, self.client_address, self._tls,
                                                     (self._multilateral or client_multilateral), self.client_id)
        self.close()

    def listen(self):
        """
        Listen on the client socket for incoming messages and handle the different MQTT messages
        """
        try:
            self._client_manager.add_status(self.client_socket, self.client_address, enums.Status.FRESH)
            while self._running:
                msg = self.client_socket.recv(1024)
                if len(msg) > 0:
                    if logger.DEBUG:
                        logger.logging.debug(f"Received raw message on Port {self.listener.port}: {msg}")
                    parsed_msg = MQTTPacketManager.parse_packet(msg, self.client_socket, self.client_address, self._client_manager)
                    if parsed_msg['identifier'] == enums.PacketIdentifer.CONNECT:
                        logger.logging.info(f"Received CONNECT message from Client {parsed_msg['client_id']} on Port {self.listener.port}: {msg}")
                        self.handle_connect(parsed_msg)
                    elif parsed_msg['identifier'] == enums.PacketIdentifer.PUBLISH:
                        logger.logging.info(f"Received PUBLISH message from Client {self.client_id} on Port {self.listener.port}: {msg}")
                        self.handle_publish(parsed_msg)
                    elif parsed_msg['identifier'] == enums.PacketIdentifer.SUBSCRIBE:
                        logger.logging.info(f"Received SUBSCRIBE message from Client {self.client_id} on Port {self.listener.port}: {msg}")
                        self.handle_subscribe(parsed_msg)
                    elif parsed_msg['identifier'] == enums.PacketIdentifer.PINGREQ:
                        logger.logging.info(f"Received PINGREQ message from Client {self.client_id} on Port {self.listener.port}: {msg}")
                        self.handle_pingreq(parsed_msg)
                    elif parsed_msg['identifier'] == enums.PacketIdentifer.DISCONNECT:
                        logger.logging.info(f"Received DISCONNECT message from Client {self.client_id} on Port {self.listener.port}: {msg}")
                        self.handle_disconnect(parsed_msg)
                    else:
                        raise MQTTMessageNotSupportedException(f'Client {self.client_address} sent a message with identifier: `{parsed_msg["identifier"]}`. Not supported, therefore ignored!')
        except OSError:
            pass
        except MQTTMessageNotSupportedException as e:
            logger.logging.error(e)
        except (IncorrectProtocolOrderException, TypeError) as e:
            logger.logging.error(e)
            self.close()


    def _determine_message_multilateral(self, parsed_msg):
        """
        Determine the multilateral security setting in the PUBLISH/SUBSCRIBE message!
        E.g if the client did no connect with multilateral security but wants to set multilateral security per message/topic.
        :param parsed_msg: a parsed version of the received message
        :return: 1 if multilateral security is set, else 0
        """
        if len(parsed_msg['properties']) > 0:
            for conn_property in parsed_msg['properties']:
                if conn_property == enums.Properties.UserProperty:
                    try:
                        multilateral = parsed_msg['properties'][conn_property]['multilateral']
                        return multilateral in ['true', '1', 't', 'y', 'yes']
                    except KeyError:
                        continue
        return 0

    def _determine_client_multilateral(self):
        """
        Determine client multilateral security setting and translate it to an understandable value for the
        handler.
        :return: 1 if client connected with multilateral security setting, else 0
        """
        properties = self._client_manager.get_user_properties(self.client_socket,
                                                              self.client_address)
        try:
            client_multilateral = properties[enums.Properties.UserProperty]['multilateral']
            if client_multilateral in ['true', '1', 't', 'y', 'yes']:
                client_multilateral = 1
            else:
                client_multilateral = 0
        except (KeyError, IndexError):
            client_multilateral = 0

        return client_multilateral

    def close(self):
        """
        Close the client thread
        """
        logger.logging.info(f"- Client {self.client_id} disconnected!")
        self.client_socket.close()
        self._stop_event.set()
        self.listener.remove_client_thread(self)

    def stopped(self):
        """
        Check if the client thread is closed.
        """
        return self._stop_event.isSet()


class Listener(object):
    """
    MQTT Listener. No security mechanisms in place.
    """
    def __init__(self, config, subscription_manager, client_manager, ip, debug=0):
        """
        Constructor for the MQTT Listener
        :param config: contains the initialized config setting
        :param ip: ip of the listener
        :param debug: debug mode on/off
        """
        self._ip = ip
        self._port = config.port
        self._multilateral = config.multilateral
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self._ip, self._port))
        self.sock.listen(ALLOWED_CONNECTIONS)
        self._running = True
        self.open_sockets = {}
        self.debug = debug
        self._subscription_manager = subscription_manager
        self._client_manager = client_manager

    def __str__(self):
        return f"MQTT Listener: [Port: {self._port}, Multilateral Security: {self._multilateral}]"

    def listen(self):
        """
        Listens for incoming socket connections to the broker port and creates a @ClientThread for each unique connection
        , that then takes over the task of listening for messages on the established socket.
        """
        logger.logging.info(f"{self.__str__()} running ...")
        while self._running:
            try:
                client_socket, client_address = self.sock.accept()
                if client_socket and client_address:
                    client_thread = ClientThread(client_socket, client_address, self, self._subscription_manager, self._client_manager, self._multilateral, self.debug)
                    self.open_sockets[client_address] = client_thread
                    client_thread.setDaemon(True)
                    client_thread.start()
            except ConnectionAbortedError:
                logger.logging.info("Closed socket connection of Listener.")

    def close_sockets(self):
        """
        Iterates over all open sockets and "closes" them, so that no open sockets and threads remain.
        ONLY USED FOR DEBUGGING PURPOSE AS DAEMON CHARACTERISTIC OF THREAD TAKES CARE OF THIS.
        """
        if len(self.open_sockets) != 0:
            logger.logging.info("--- Closing open client connections")
            for index, client_thread in enumerate(self.open_sockets):
                logger.logging.info(f"\t --- Connection {index+1}/{len(self.open_sockets)} closed")
            logger.logging.info("--- All open client connections were successfully closed.")
        self.sock.close()

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, value):
        self._running = value

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, value):
        self._port = value

    def remove_client_thread(self, client_thread):
        self.open_sockets.pop(client_thread.client_address)
        logger.logging.info(f"- Successfully closed ClientThread, that managed '{client_thread.client_id}'")


class TLSListener(Listener):
    """
    TLS MQTT Listener. Handles the TLS connection of clients and then starts a @ClientThread for each connection, that
    then handles the message handling.
    """
    def __init__(self, config, subscription_manager, client_manager, ip, debug=0):
        super().__init__(config, subscription_manager, client_manager, ip, debug)
        self._cacert = config.cacert
        self._servercert = config.servercert
        self._serverkey = config.serverkey

        # TLS socket establishment
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.context.load_cert_chain(certfile=self._servercert, keyfile=self._serverkey)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self._ip, self._port))
        self.sock.listen(ALLOWED_CONNECTIONS)

    def __str__(self):
        return "TLS" + super().__str__()

    def listen(self):
        """
        Listens for incoming TLS socket connections to the secure broker port and creates a TLS @ClientThread for
        each unique connection, that then takes over the task of listening for messages on the established TLS socket.
        """
        logger.logging.info(f"{self.__str__()} running ...")
        while self._running:
            try:
                client_socket, client_address = self.sock.accept()
                try:
                    connstream = self.context.wrap_socket(client_socket, server_side=True)
                    if client_socket and client_address and connstream:
                        client_thread = ClientThread(connstream, client_address, self, self._subscription_manager, self._client_manager, self._multilateral, self.debug, tls=1)
                        self.open_sockets[client_address] = client_thread
                        client_thread.setDaemon(True)
                        client_thread.start()
                except ssl.SSLError:
                    logger.logging.error(f"Client {client_address} tried to connect to Port {self._port} (=TLS) via insecure channel. Connection refused.")
                    client_socket.close()
            except ConnectionAbortedError:
                logger.logging.info("Closed socket connection of TLS Listener.")