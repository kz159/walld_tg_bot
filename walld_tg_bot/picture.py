import requests

class AttrDisplay:
    def gatherAttrs(self):
        attrs = []
        for key in sorted(self.__dict__):
            attrs.append('%s=%s' % (key, getattr(self, key)))
        return ', '.join(attrs)
    
    def __repr__(self):
        return '[%s: %s]' % (self.__class__.__name__, self.gatherAttrs())

class Picture(AttrDisplay):
    def __init__(self, service, source, author, height, width, url, id):
        self.id = id
        self.service = service
        self.source = source
        self.author = author
        self.height = height
        self.width = width
        self.url = url
        self.colours = None

    @classmethod
    def from_pexel(cls, pexel):
        return cls(service='Pexel',
                   source=pexel.url,
                   author=pexel.photographer,
                   height=pexel.height,
                   width=pexel.width,
                   url=pexel.src['original'],
                   id=pexel.id)

    def download(self):
        pass

    def calc_colour(self):
        pass
