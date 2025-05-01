from __future__ import annotations

import re

from pydantic import BaseModel

pattern = re.compile(
    r"\{(?P<name>.*?):\s*(?P<value>.*?)\}", re.DOTALL
)


class Node(BaseModel):
    name: str
    value: str
    start: int
    end: int

    @property
    def position(self) -> tuple[int, int]:
        return self.start, self.end

    def __repr__(self) -> str:
        return f"<Node {self.name=} {self.value=} {self.start=} {self.end=}>"

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return (
            self.name == other.name
            and self.value == other.value
        )

    @classmethod
    def find(cls, template: str) -> list[Node]:
        """
        Find all nodes in the template.
        """
        return [
            cls(
                **match.groupdict(),
                start=match.start(),
                end=match.end(),
            )
            for match in pattern.finditer(template)
        ]
