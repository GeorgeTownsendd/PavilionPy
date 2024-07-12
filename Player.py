import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Union


@dataclass
class PlayerState:
    id: uuid.UUID
    attributes: Dict[str, Optional[Union[int, float, str]]]


class Player:
    def __init__(self, player_id: str):
        self.player_id = str(player_id)
        self.states: List[PlayerState] = []
        self.current_state: Optional[PlayerState] = None

    def __getattr__(self, name):
        if self.current_state and name in self.current_state.attributes:
            return self.current_state.attributes[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.get_attribute(key)
        elif isinstance(key, (list, tuple)):
            return {k: self.get_attribute(k) for k in key}
        else:
            raise TypeError("Key must be a string or a list/tuple of strings")

    def get_attribute(self, attr_name, default=None):
        if self.current_state and attr_name in self.current_state.attributes:
            return self.current_state.attributes[attr_name]
        return default

    def add_state(self, attributes: Dict[str, Optional[Union[int, float, str]]]) -> uuid.UUID:
        if 'PlayerID' not in attributes:
            raise ValueError("PlayerID must be included in the attributes")

        if str(attributes['PlayerID']) != self.player_id:
            raise ValueError(
                f"PlayerID in attributes ({attributes['PlayerID']}) does not match Player's ID ({self.player_id})")

        state_id = uuid.uuid4()
        new_state = PlayerState(id=state_id, attributes=attributes)
        self.states.append(new_state)
        self.current_state = new_state
        return state_id

    def get_state(self, identifier: Union[uuid.UUID, int]) -> Optional[PlayerState]:
        if isinstance(identifier, uuid.UUID):
            return next((state for state in self.states if state.id == identifier), None)
        elif isinstance(identifier, int) and 1 <= identifier <= len(self.states):
            return self.states[identifier - 1]
        return None

    def set_state(self, identifier: Union[uuid.UUID, int]) -> bool:
        state = self.get_state(identifier)
        if state:
            self.current_state = state
            return True
        return False

    @property
    def latest_state(self) -> Optional[PlayerState]:
        return self.states[-1] if self.states else None

    @property
    def loaded(self) -> bool:
        return bool(self.states)

    @property
    def state_count(self) -> int:
        return len(self.states)