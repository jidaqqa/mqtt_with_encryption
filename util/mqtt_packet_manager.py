import util.enums as enums
import util.logger as logger
import util.authentication_plugin as authentication
import struct


class MQTTPacketManager(object):
    @staticmethod
    def parse_packet(packet, client_socket, client_address, client_manager):
        """
        Parse the received packet. Return a meaningful and understandable representation of the received packet bytes
        :param client_manager: manager of the client connections (@ClientManager)
        :param client_socket: socket of the publishing client
        :param client_address: address of the publishing client
        :param packet: The received packet
        :return: dictionary containing all important information of the received packet
        """
        fixed_header = packet[0]
        control_packet_type = (fixed_header >> 4) & 0xf
        control_packet_flags = fixed_header & 0xf
        remaining_length = packet[1]
        if logger.DEBUG:
            logger.logging.debug(
                f"\tControl_packet_type: {enums.PacketIdentifer(control_packet_type)} with flags: {control_packet_flags} and remaining length: {remaining_length}")
        if enums.PacketIdentifer(control_packet_type) == enums.PacketIdentifer.CONNECT:
            return MQTTPacketManager.parse_connect(packet[2:], remaining_length)
        elif enums.PacketIdentifer(control_packet_type) == enums.PacketIdentifer.PUBLISH:
            return MQTTPacketManager.parse_publish(packet, remaining_length, client_socket, client_address, client_manager)
        elif enums.PacketIdentifer(control_packet_type) == enums.PacketIdentifer.SUBSCRIBE:
            return MQTTPacketManager.parse_subscribe(packet[2:], remaining_length, client_socket, client_address, client_manager)
        elif enums.PacketIdentifer(control_packet_type) == enums.PacketIdentifer.PINGREQ:
            return MQTTPacketManager.parse_pingreq()
        elif enums.PacketIdentifer(control_packet_type) == enums.PacketIdentifer.DISCONNECT:
            return MQTTPacketManager.parse_disconnect()
        else:
            return {'identifier': "DEBUG MODE ACTIVATED"}

    @staticmethod
    def prepare_pingresp():
        """
        Prepare the PINGRESP packet according to the MQTTv5.0 specification Chapter 3.13 PINGRESP – PING response
        :return: PINGRESP packet that should be sent to the client (as bytes)
        """
        control_packet_type = enums.PacketIdentifer.PINGRESP.value << 4
        control_packet_flags = 0
        fixed_header = control_packet_type | control_packet_flags
        remaining_length = 0
        return struct.pack('BB', fixed_header, remaining_length)

    @staticmethod
    def prepare_connack(parsed_msg, authenticated):
        """
        Prepare the CONNACK packet according to the MQTTv5.0 specification Chapter 3.2 CONNACK – Connect acknowledgement
        :param authenticated: To check if the user has the right to connect to the broker
        :param parsed_msg: FOR FUTURE FUNCTIONALITY
        :return: CONNACK packet that should be sent to the client (as bytes)
        """
        # fixed header
        control_packet_type = enums.PacketIdentifer.CONNACK.value << 4
        control_packet_flags = 0
        fixed_header = control_packet_type | control_packet_flags
        remaining_length = 0
        # Connect Acknowledge Flags
        flags = 0
        remaining_length += 1
        # Reason Code
        if authenticated:
            reason_code = enums.ConnectReasonCodes.Success.value
        else:
            reason_code = enums.ConnectReasonCodes.NotAuthorized.value
        remaining_length += 1

        return struct.pack('BBBB', fixed_header, remaining_length, flags, reason_code)

    @staticmethod
    def prepare_suback(parsed_msg):
        """
        Prepare the SUBACK packet according to the MQTTv5.0 specification Chapter 3.9 SUBACK - Subscribe acknowledgement
        :param parsed_msg: parsed version of the received message
        :return: SUBACK packet that should be sent to the client (as bytes)
        """
        control_packet_type = enums.PacketIdentifer.SUBACK.value << 4
        control_packet_flags = 0
        fixed_header = control_packet_type | control_packet_flags
        remaining_length = 0
        # packet identifier of the subscribe message
        packet_identifier = parsed_msg['packet_identifier']
        remaining_length += 2
        # properties
        property_length = 0
        remaining_length += 1
        # payload
        payload = enums.SubackReasonCodes.GrantedQOS0.value
        remaining_length += 1
        return struct.pack('>BBHBB', fixed_header, remaining_length, packet_identifier, property_length, payload)

    @staticmethod
    def parse_disconnect():
        """
        Parse the DISCONNECT message according to the MQTTv5.0 specification Chapter 3.14 DISCONNECT - Disconnect notification.
        :return: a dictionary containing meaningful values of the received packet
        """
        parsed_msg = {'identifier': enums.PacketIdentifer.DISCONNECT}
        return parsed_msg

    @staticmethod
    def parse_publish(packet, remaining_length, client_socket, client_address, client_manager):
        """
        Parse the PUBLISH message according to the MQTTv5.0 specification Chapter 3.3 PUBLISH – Publish message. Also
        supports MQTTv3.1.1.
        :param client_manager: manager of the client connections (@ClientManager)
        :param client_socket: socket of the publishing client
        :param client_address: address of the publishing client
        :param packet: the raw bytes packet that was received
        :param remaining_length: remaining length of the packet
        :return: a dictionary containing meaningful values of the received packet (identifier, topic, properties, payload)
        """
        parsed_msg = {'identifier': enums.PacketIdentifer.PUBLISH, 'raw_packet': packet}
        current_pos = 2
        current_pos, parsed_msg['topic'] = MQTTPacketManager.extract_topic(packet, current_pos)
        parsed_msg['properties'] = {}

        if client_manager.get_user_properties(client_socket, client_address)[enums.Properties.Version] == enums.Version.MQTTv5.value:
            current_pos, properties = MQTTPacketManager.extract_properties(packet, current_pos)
            if len(properties) != 0:
                for user_property in properties:
                    parsed_msg['properties'][user_property] = properties[user_property]

        current_pos, parsed_msg['payload'] = MQTTPacketManager.extract_publish_payload(packet, current_pos)
        return parsed_msg

    @staticmethod
    def parse_subscribe(packet, remaining_length, client_socket, client_address, client_manager):
        """
        Parse the SUBSCRIBE message according to the MQTTv5.0 specification Chapter 3.8 SUBSCRIBE - Subscribe request
        Also supports MQTTv3.1.1
        :param client_manager: manager of the client connections (@ClientManager)
        :param client_socket: socket of the publishing client
        :param client_address: address of the publishing client
        :param packet: the raw bytes packet that was received
        :param remaining_length: remaining length of the packet
        :return: a dictionary containing meaningful values of the received packet (identifier, packet_identifier, properties, topic, options)
        """
        parsed_msg = {'identifier': enums.PacketIdentifer.SUBSCRIBE}
        current_pos = 0
        current_pos, parsed_msg['packet_identifier'] = MQTTPacketManager.extract_packet_identifier(packet, current_pos)
        parsed_msg['properties'] = {}

        if client_manager.get_user_properties(client_socket, client_address)[enums.Properties.Version] == enums.Version.MQTTv5.value:
            current_pos, properties = MQTTPacketManager.extract_subscribe_properties(packet, current_pos)
            if len(properties) != 0:
                for user_property in properties:
                    parsed_msg['properties'][user_property] = properties[user_property]

        current_pos, parsed_msg['topic'] = MQTTPacketManager.extract_topic(packet, current_pos)
        current_pos, parsed_msg['options'] = MQTTPacketManager.extract_subscribe_options(packet, current_pos)
        return parsed_msg

    @staticmethod
    def parse_pingreq():
        """
        Parse the PINGREQ message according to the MQTTv5.0 specification Chapter 3.12 PINGREQ – PING request
        :return: a dictionary containing meaningful values of the received packet (identifier)
        """
        parsed_msg = {'identifier': enums.PacketIdentifer.PINGREQ}
        return parsed_msg

    @staticmethod
    def parse_connect(packet, remaining_length):
        """
        Parse the CONNECT message. Translate the received bytes to meaningful values according to the
        MQTTv5.0 specification Chapter 3.1 CONNECT – Connection Request. Also supports MQTT 3.1.1.
        :param packet: the received packet
        :param remaining_length: the size of the packet
        :return: a dictionary containing meaningful values of the received packet
        """
        parsed_msg = {'identifier': enums.PacketIdentifer.CONNECT}
        current_pos = 0
        current_pos, parsed_msg['protocol'] = MQTTPacketManager.extract_protocol_name(packet, current_pos)
        current_pos, parsed_msg['version'] = MQTTPacketManager.extract_protocol_version(packet, current_pos)
        current_pos, parsed_msg['connect_flags'] = MQTTPacketManager.extract_connect_flags(packet, current_pos)
        current_pos, parsed_msg['keep_alive'] = MQTTPacketManager.extract_keep_alive(packet, current_pos)
        parsed_msg['properties'] = {}

        if parsed_msg['version'] == enums.Version.MQTTv5.value:
            current_pos, properties = MQTTPacketManager.extract_properties(packet, current_pos)
            if len(properties) != 0:
                for user_property in properties:
                    parsed_msg['properties'][user_property] = properties[user_property]
        current_pos, parsed_msg['client_id'] = MQTTPacketManager.extract_client_id(packet, current_pos)
        current_pos, parsed_msg['username'] = MQTTPacketManager.extract_username(packet, current_pos)
        current_pos, parsed_msg['password'] = MQTTPacketManager.extract_password(packet, current_pos)

        return parsed_msg

    @staticmethod
    def extract_subscribe_properties(packet, position):
        """
        Extract all Subscribe properties from the received packet according to the MQTTv5.0 specification Chapter 3.8.2.1 SUBSCRIBE Properties
        :param packet: the received packet from the client
        :param position: current byte position in the packet
        :return: updated position and the properties in form of a dictionary
        """
        property_length = packet[position]
        if logger.DEBUG:
            logger.logging.debug(f"\tProperty length: {property_length}")

        position += 1

        properties = {}
        property_value_length = property_length - 1
        current_pos = position
        max_byte = current_pos + property_value_length
        while current_pos < max_byte:
            identifier = enums.Properties(packet[current_pos])
            # Extract User Properties
            if identifier == enums.Properties.UserProperty:
                current_pos += 2
                length_first_user_property = packet[current_pos]
                current_pos += 1
                first_user_property = packet[current_pos : current_pos+length_first_user_property].decode('utf-8').lower()
                current_pos += length_first_user_property
                current_pos += 1
                length_second_user_property = packet[current_pos]
                current_pos += 1
                second_user_property = packet[current_pos : current_pos + length_second_user_property].decode("utf-8").lower()
                current_pos += length_second_user_property
                properties[identifier] = {first_user_property: second_user_property}
                if logger.DEBUG:
                    logger.logging.debug(f"\t\tIdentifier: {identifier}")
                    logger.logging.debug(
                        f"\t\tFirst: length: {length_first_user_property}, UserProperty: {first_user_property}")
                    logger.logging.debug(
                        f"\t\tSecond: length: {length_second_user_property}, UserProperty: {second_user_property}")
                    logger.logging.debug(f"\t\tCurrentbyte: {current_pos}, Maxbyte: {max_byte} ... values: "
                                         f"{5 + length_first_user_property + length_second_user_property}/{property_length}")

            # Extract Subscription Identifier
            elif identifier == enums.Properties.SubscriptionIdentifier:
                current_pos += 1
                user_property_value = packet[current_pos]
                current_pos += 1
                properties[identifier] = user_property_value

                if logger.DEBUG:
                    logger.logging.debug(f"\t\tIdentifier: {identifier}")
                    logger.logging.debug(f"\t\tValue: {user_property_value}")

        return current_pos, properties

    @staticmethod
    def extract_subscribe_options(packet, position):
        """
        Extract all Subscribe options from the received packet according to the MQTTv5.0 specification Chapter 3.8.3.1 Subscription Options
        :param packet: the received packet from the client
        :param position: current byte position in the packet
        :return: updated position and the option flags (byte)
        """
        option_flags = packet[position]
        position += 1
        return position, option_flags

    @staticmethod
    def extract_packet_identifier(packet, position):
        """
        Extract the Subscribe packet identifier from the received packet according to the MQTTv5.0 specification Chapter 3.8.2 SUBSCRIBE Variable Header
        :param packet: the received packet from the client
        :param position: current byte position in the packet
        :return: updated position and the packet identifier
        """
        packet_identifier_msb = packet[position]
        position += 1
        packet_identifier_lsb = packet[position]
        position += 1
        packet_identifier = (packet_identifier_msb << 8) | packet_identifier_lsb
        if logger.DEBUG:
            logger.logging.debug(f"\tPacket Identifier: {packet_identifier}")
        return position, packet_identifier

    @staticmethod
    def extract_topic(packet, position):
        """
        Extract the Topic from SUBSCRIBE and PUBLISH packets according to the MQTTv5.0 specification Chapter 3.3.2.1 Topic Name and 3.8.3 SUBSCRIBE Payload
        :param packet: the received packet from the client
        :param position: current byte position in the packet
        :return: updated position and the topic
        """
        length_msb = packet[position]
        position += 1
        length_lsb = packet[position]
        position += 1
        length = (length_msb << 8) | length_lsb
        topic = packet[position: position + length].decode('utf-8')
        position += length
        if logger.DEBUG:
            logger.logging.debug(f"\tTopic: {topic}")
        return position, topic

    @staticmethod
    def extract_publish_payload(packet, position):
        """
        Extract the Payload from a PUBLISH packet according to the MQTTv5.0 specification Chapter 3.3.3 PUBLISH Payload
        :param packet: the received packet from the client
        :param position: current byte position in the packet
        :return: updated position and the payload of the PUBLISH packet
        """
        payload = packet[position:].decode('utf-8')
        position = position + len(payload)
        if logger.DEBUG:
            logger.logging.debug(f"\tPayload: {payload}")
        return position, payload

    @staticmethod
    def extract_protocol_name(packet, position):
        """
        Extract the protocol name from the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.2.1 Protocol Name. Also supports MQTTv3.1.1 extraction.
        :param packet: the received packet
        :param position: the current position in the packet
        :return: updated position and the protocol name (as str)
        """
        length_msb = packet[position]
        position += 1
        length_lsb = packet[position]
        position += 1
        length_name = (length_msb << 4) | length_lsb
        protocol_name = ""
        if length_name != 0:
            protocol_name = packet[position:position + length_name].decode('utf-8')  # MQTT
            position += length_name
        if logger.DEBUG:
            logger.logging.debug(f"\tMSB: {length_msb}, LSB: {length_lsb}, protocol_name: {protocol_name}")
        return position, protocol_name

    @staticmethod
    def extract_protocol_version(packet, position):
        """
        Extract the protocol version from the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.2.2 Protocol Version
        :param packet: the received packet
        :param position: the current position in the packet
        :return: updated position and the protocol version (as int)
        """
        protocol_version = int(packet[position])  # 0x05
        if logger.DEBUG:
            logger.logging.debug(f"\tProtocol Version: {protocol_version}")
        position += 1
        return position, protocol_version

    @staticmethod
    def extract_connect_flags(packet, position):
        """
        Extract the connect flags from the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.2.3 Connect Flags
        :param packet: the received packet
        :param position: the current position in the packet
        :return: updated position and the connect flags (as int)
        """
        connect_flags = packet[position]  # 0x00 / 0x01
        bits = bin(connect_flags)[2:].zfill(8)
        username_flag = int(bits[0])
        password_flag = int(bits[1])
        will_retain = int(bits[2])
        will_qos = int(bits[3:5])
        will_flag = int(bits[5])
        clean_start = int(bits[6])

        if logger.DEBUG:
            logger.logging.debug(
                f"\tConnect flags: username_flag: {username_flag}, password_flag: {password_flag}, will_retain: {will_retain}"
                f"will_qos: {will_qos}, will_flag: {will_flag}, clean_start: {clean_start}")

        position += 1
        return position, connect_flags

    @staticmethod
    def extract_keep_alive(packet, position):
        """
        Extract the Keep_alive value from the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.2.10 Keep Alive
        :param packet: the received packet
        :param position: the current position in the packet
        :return: updated position and the keep_alive value (as int)
        """
        keep_alive_msb = packet[position]  # 0x00
        position += 1
        keep_alive_lsb = packet[position]  # <
        position += 1
        keep_alive = (keep_alive_msb << 8) | keep_alive_lsb
        if logger.DEBUG:
            logger.logging.debug(f"\tMSB: {keep_alive_msb}, LSB: {keep_alive_lsb} = Keep Alive: {keep_alive}")

        return position, keep_alive

    @staticmethod
    def extract_properties(packet, position):
        """
        Extract all additional properties of the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.2.11 CONNECT Properties
        :param packet: the received packet
        :param position: current position in the packet
        :return: updated position and all additional properties (as dictionary)
        """
        #
        property_length = packet[position]  # \n
        if logger.DEBUG:
            logger.logging.debug(f"\tProperty length: {property_length}")
        position += 1
        properties = {}
        current_pos = position
        max_byte = current_pos + property_length
        while current_pos < max_byte:
            identifier = enums.Properties(packet[current_pos])
            current_pos += 1
            # unused_field = packet[current_pos]
            current_pos += 1
            length_first_user_property = packet[current_pos]
            current_pos += 1
            first_user_property = packet[current_pos: current_pos + length_first_user_property].decode('utf-8').lower()
            current_pos += length_first_user_property
            # unused_field = packet[current_pos]
            current_pos += 1
            length_second_user_property = packet[current_pos]
            current_pos += 1
            second_user_property = packet[current_pos: current_pos + length_second_user_property].decode(
                'utf-8').lower()
            current_pos += length_second_user_property
            properties[identifier] = {first_user_property: second_user_property}

            if logger.DEBUG:
                logger.logging.debug(f"\t\tIdentifier: {identifier}")
                logger.logging.debug(
                    f"\t\tFirst: length: {length_first_user_property}, UserProperty: {first_user_property}")
                logger.logging.debug(
                    f"\t\tSecond: length: {length_second_user_property}, UserProperty: {second_user_property}")
                logger.logging.debug(f"\t\tCurrentbyte: {current_pos}, Maxbyte: {max_byte} ... values: "
                                     f"{5 + length_first_user_property + length_second_user_property}/{property_length}")

        return current_pos, properties

    @staticmethod
    def extract_client_id(packet, position):
        """
        Extract the client id from the received packet (CONNECT) according to the MQTTv5.0
        specification Chapter 3.1.3.1 Client Identifier (ClientID)
        :param packet: the received packet
        :param position: current position in the packet
        :return: updated position and the client id (str)
        """
        nothing = packet[position]
        position += 1
        length_client_id = packet[position]
        position += 1
        client_id = packet[position: position + length_client_id].decode('utf-8')
        position += length_client_id
        if logger.DEBUG:
            logger.logging.debug(f"\tClientID: {client_id}")
        return position, client_id

    def extract_username(packet, position):

        position += 1
        length_username = packet[position]
        position += 1
        username = packet[position: position + length_username].decode('utf-8')
        position += length_username
        if logger.DEBUG:
            logger.logging.debug(f"\tClient-Username: {username}")

        return position, username

    def extract_password(packet, position):

        position += 1
        length_password = packet[position]
        position += 1
        password = packet[position: position + length_password].decode('utf-8')
        position += length_password

        if logger.DEBUG:
            logger.logging.debug(f"\tClient-Password: {password}")

        return position, password

