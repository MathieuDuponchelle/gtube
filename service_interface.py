class ServiceInterface:
    def search (self, words):
        raise NotImplementedError

    def authenticate(self):
        raise NotImplementedError
