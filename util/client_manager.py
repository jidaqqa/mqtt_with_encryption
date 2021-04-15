from util.exceptions import IncorrectProtocolOrderException
import util.enums as enums


class ClientManager(object):
    def __init__(self):
        self._client_status = {}
        self._client_property = {}

    @property
    def client_status(self):
        return self._client_status

    @client_status.setter
    def client_status(self, value):
        self._client_status = value

    @property
    def client_property(self):
        return self._client_property

    @client_property.setter
    def client_property(self, value):
        self._client_property = value

    def add_user_property(self, client_socket, client_address, properties):
        """
        Add the connection user properties to the status manager storage.
        :param client_socket: client socket of the client
        :param client_address: client address of the client
        :param properties: connection properties of the client (dictionary of dictionaries)
        """
        if len(properties) > 0:
            for conn_property in properties:
                if (client_socket, client_address) in self._client_property:
                    self._client_property[(client_socket, client_address)][conn_property] = properties[conn_property]
                else:
                    self._client_property[(client_socket, client_address)] = {conn_property : properties[conn_property]}

    def get_user_properties(self, client_socket, client_address):
        """
        Get the connection user properties of a specific client
        :param client_socket: socket of the client
        :param client_address: address of the client
        :return: dictionary of all client connection properties
        """
        try:
            return self._client_property[(client_socket, client_address)]
        except KeyError:
            return {}

    @staticmethod
    def check_status_order_validity(old_status, new_status):
        """
        Check if the new_status fulfills the order of the MQTT protocol in respect to the old_status
        :param self: NOT USED
        :param old_status: old protocol status of the client
        :param new_status: new protocol status of the client
        :return: True, if new_status is subsequent to old_status (according to MQTTv5.0 specifications)
                 False: if new_status does not fulfill the MQTTv5.0 order specifications
        """
        if old_status:
            if old_status != enums.Status.FRESH and old_status.value <= new_status.value:
                return True
            elif old_status == enums.Status.FRESH and new_status == enums.Status.CONN_RECV:
                return True
            else:
                return False
        else:
            if new_status == enums.Status.FRESH:
                return True
            else:
                return False

    def add_status(self, client_socket, client_address, new_status):
        """
        Adds a new status for a client
        :param client_socket: client socket on which the client is currently connected
        :param client_address: client's current address and port
        :param new_status: the new status that should be set
        :return:
            @IncorrectProtocolOrderException: if new_status does not fulfill the MQTTv5.0 order specifications
            @TypeError: if new_status is not supported
            Nothing: if new_status was successfully set
        """
        if (client_socket, client_address) in self._client_status:
            if isinstance(new_status, enums.Status):
                current_status = self._client_status[(client_socket, client_address)]
                if self.check_status_order_validity(current_status, new_status):
                    self._client_status[(client_socket, client_address)] = new_status
                else:
                    raise IncorrectProtocolOrderException(f"Invalid protocol order: {new_status} after {current_status}.")
            else:
                raise TypeError('new_status must be an instance of Status Enum.')
        else:
            if self.check_status_order_validity(None, new_status):
                self._client_status[(client_socket, client_address)] = new_status
            else:
                raise IncorrectProtocolOrderException(f"Invalid protocol order: {new_status} as initial status. Expected 'FRESH'")

    def get_client_status(self, client_socket, client_address):
        """
        Returns the current status of a certain client
        :param client_socket: client socket of the client
        :param client_address: client address of the client
        :return: current status or None if client does not exist
        """
        try:
            return self._client_status[(client_socket, client_address)]
        except IndexError:
            return None