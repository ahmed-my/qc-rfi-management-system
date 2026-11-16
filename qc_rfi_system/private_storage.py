
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from pathlib import Path


class PrivateMediaStorage(FileSystemStorage):

    def __init__(self, *args, **kwargs):
        kwargs["location"] = Path(settings.BASE_DIR) / "private_media"
        kwargs["base_url"] = None
        super().__init__(*args, **kwargs)

    @property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError(
            "Private files cannot be accessed through public URLs."
        )
