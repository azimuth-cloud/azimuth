class KeyStore(object):
    def __init__(self, key=None):
        self.key = key

    def get_key(self, username):
        return self.key
