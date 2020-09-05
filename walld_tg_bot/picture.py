from dataclasses import dataclass
from typing import List, Optional

# TODO move this file into walld_utils


@dataclass
class Picture:
    id: int
    service: str
    source: str
    author: str
    height: str
    width: str
    url: str
    colours: Optional[List[bytes]]  # TODO DO WE NEED THIS?

    @classmethod
    def from_pexel(cls, pexel):
        return cls(service='Pexel',
                   source=pexel.url,
                   author=pexel.photographer,
                   height=pexel.height,
                   width=pexel.width,
                   url=pexel.src['original'],
                   id=pexel.id)
