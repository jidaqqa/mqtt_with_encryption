import util.logger as logger


class Authentication(object):

    @staticmethod
    def read_password_file(password_file, username, password):
        authenticated = False
        users = dict()
        try:
            with open(password_file) as f:
                for l in f:
                    line = l.strip()
                    if not line.startswith('#'):  # Allow comments in files
                        usr, pwd = line.split(sep=":", maxsplit=3)
                        users[usr] = pwd

                if username in users.keys():
                    if users[username] == password:
                        authenticated = True
                    else:
                        logger.logging.debug("Password is not correct, please check it!")
                else:
                    logger.logging.debug("username is not correct, please check it!")
        except FileNotFoundError:
            logger.logging.debug("Password file %s not found" % password_file)
        return authenticated
