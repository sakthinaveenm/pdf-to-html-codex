from abc import ABC, abstractmethod
from pathlib import Path
from app.schemas.document import Document, Options

class PDFConverter(ABC):
    name: str
    @abstractmethod
    def convert(self, path: Path, document: Document, options: Options, output: Path) -> Document: ...
    @abstractmethod
    def check_availability(self) -> bool: ...
    def get_capabilities(self) -> dict:
        return {'name':self.name, 'installed':self.check_availability()}
