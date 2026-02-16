class ServiceCodeNotResolvedException(Exception):
    def __init__(self, message: str = "Service code could not be resolved"):
        self.message = message
        super().__init__(message)