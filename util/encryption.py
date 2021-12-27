from cryptography.fernet import Fernet
import util.logger as logger
import base64

class EncryptionDecryption(object):

    @staticmethod
    def read_key_file(key_file):
        keys = dict()
        with open(key_file) as f:
            logger.logging.debug(f"\tReading user database from %s" % key_file)
            for l in f:
                line = l.strip()
                if not line.startswith('#'):  # Allow comments in files
                    topic, key = line.split(sep=":", maxsplit=1)
                    keys[topic] = key
        return keys

    @staticmethod
    def encrypt_method(topic, key_file, message):

        keys = dict()
        cipher_key = None
        with open(key_file) as f:
            logger.logging.debug(f"\tReading user database from %s" % key_file)
            for l in f:
                line = l.strip()
                if not line.startswith('#'):  # Allow comments in files
                    topic, key = line.split(sep=":", maxsplit=1)
                    keys[topic] = key

        if topic in keys.keys():
            cipher_key = keys[topic]

        cipher = Fernet(cipher_key)
        message = bytes(message, 'utf-8')
        encrypted_message = cipher.encrypt(message)
        logger.logging.info(f"\tEncrypted message: %s" % encrypted_message)
        return encrypted_message

    @staticmethod
    def decrypt_method(topic, key_file, message):

        keys = dict()
        cipher_key = None
        with open(key_file) as f:
            for l in f:
                line = l.strip()
                if not line.startswith('#'):  # Allow comments in files
                    topic, key = line.split(sep=":", maxsplit=1)
                    keys[topic] = key

        if topic in keys.keys():
            cipher_key = keys[topic]

        cipher = Fernet(cipher_key)
        message = bytes(message, 'utf-8')
        decrypted_message = cipher.decrypt(message)

        return decrypted_message

