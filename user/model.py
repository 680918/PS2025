from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class User:
    name: str
    email: str
    user_id: str = field(default_factory=lambda: str(uuid4()))
