class EkiUtils:
    def is_float(self, element):
        try:
            float(element)
            return True
        except ValueError:
            return False
