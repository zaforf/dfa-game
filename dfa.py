import yaml
import queue
from pydantic import BaseModel, ValidationError

class State:
    def __init__(self, name: str):
        self.name: str = name
        self.accepting: bool = False
        self.transition: dict[str, State] = {}

class DFASchema(BaseModel):
    alphabet: list[str]
    states: list[str]
    initial_state: str
    accepting_states: list[str]
    transitions: dict[str, dict[str, str]]

class DFA:
    # states
    # alphabet
    # transition function
    # initial states
    # accepting states

    def __init__(self, alphabet = None, initial_state = None, states = None):
        self.alphabet: tuple[str] | None = alphabet
        self.initial_state: State | None = initial_state
        self.states: dict[str, State] = states or {}

    def load(self, source: str, is_file: bool = True) -> dict[str, object]:
        try:
            if is_file:
                with open(source, 'r') as file:
                    data = yaml.load(file, Loader=yaml.BaseLoader)
            else:
                data = yaml.load(source, Loader=yaml.BaseLoader)
        except yaml.YAMLError as e:
            return {
                "success": False,
                "errors": [f"YAML parsing error: {str(e).replace(chr(10), ' ')}"]
            }

        data = data or {}
        try:
            DFASchema(**data)
        except ValidationError as e:
            clean_errors = []
            for err in e.errors():
                # err['loc'] is a tuple like ('transitions', 'q00', '1')
                field = " -> ".join(str(x) for x in err['loc'])
                message = err['msg']
                clean_errors.append(f"Field '{field}': {message}")

            return {
                "success": False, 
                "errors": clean_errors
            }

        errors: list[str] = []

        # create alphabet and ensure symbols are single characters
        self.alphabet = tuple(data['alphabet'])
        for symbol in self.alphabet:
            if len(symbol) != 1:
                errors.append(f"Symbol '{symbol}' is not a single character.")

        # create states with names
        for state in data['states']:
            self.states[state] = State(state)

        # set initial state
        if data['initial_state'] not in self.states:
            errors.append(f"Initial state '{data['initial_state']}' not in states.")
        else:
            self.initial_state = self.states[data['initial_state']]

        # set accepting states
        for accepting in data['accepting_states']:
            if accepting not in self.states:
                errors.append(f"Accepting state '{accepting}' not in states.")
            else:
                self.states[accepting].accepting = True

        # define transition function
        for state, transitions in data['transitions'].items():
            if state not in self.states:
                errors.append(f"State '{state}' in transition function not in states.")
                continue
            for symbol, dest in transitions.items():
                if dest not in self.states:
                    errors.append(f"State '{dest}' in transition function not in states.")
                    continue
                self.states[state].transition[symbol] = self.states[dest]

        # verify all states have transitions for every symbol
        if errors == []:
            for state in self.states.values():
                for symbol in self.alphabet:
                    if symbol not in state.transition:
                        errors.append(f"State '{state.name}' missing transition for symbol '{symbol}'.")

        return {
            "success": len(errors) == 0,
            "errors": errors
        }
    
    def accepts(self, input_string: str):
        if self.initial_state is None or self.alphabet is None:
            raise RuntimeError("DFA not loaded. Call load() successfully first.")
        
        current_state: State = self.initial_state
        for symbol in input_string:
            if symbol not in self.alphabet:
                return {
                    "success": False,
                    "errors": [f"Symbol '{symbol}' not in alphabet."]
                }

            current_state = current_state.transition[symbol]

        return {
            "success": True,
            "accepted": current_state.accepting,
            "errors": []
        }

    def __invert__(self) -> 'DFA':
        if self.initial_state is None or self.alphabet is None:
            raise RuntimeError("DFA not loaded. Call load() successfully first.")

        new_states = {name: State(name) for name in self.states}

        for name, old_state in self.states.items():
            new_state = new_states[name]
            new_state.accepting = not old_state.accepting

            for symbol, dest in old_state.transition.items():
                new_state.transition[symbol] = new_states[dest.name]

        return DFA(
            alphabet=self.alphabet,
            initial_state=new_states[self.initial_state.name],
            states=new_states
        )
    
    def __or__(self, other: 'DFA') -> 'DFA':
        if self.initial_state is None or self.alphabet is None:
            raise RuntimeError("DFA not loaded. Call load() successfully first.")
        if other.initial_state is None or other.alphabet is None:
            raise RuntimeError("Other DFA not loaded. Call load() successfully first.")
        if self.alphabet != other.alphabet:
            raise ValueError("Alphabets of both DFAs must be the same.")

        new_states = {}
        for name1, state1 in self.states.items():
            for name2, state2 in other.states.items():
                new_name = f"{name1}_{name2}"
                new_state = State(new_name)
                new_state.accepting = state1.accepting or state2.accepting
                new_states[new_name] = new_state

        for name1, state1 in self.states.items():
            for name2, state2 in other.states.items():
                new_name = f"{name1}_{name2}"
                new_state = new_states[new_name]

                for symbol in self.alphabet:
                    dest1 = state1.transition[symbol]
                    dest2 = state2.transition[symbol]
                    dest_name = f"{dest1.name}_{dest2.name}"
                    new_state.transition[symbol] = new_states[dest_name]

        return DFA(
            alphabet=self.alphabet,
            initial_state=new_states[f"{self.initial_state.name}_{other.initial_state.name}"],
            states=new_states
        )

    def __and__(self, other: 'DFA') -> 'DFA':
        return ~(~self | ~other)

    def __xor__(self, other: 'DFA') -> 'DFA':
        return (self | other) & ~(self & other)
    
    def get_example(self, accepted: bool = True) -> str | None:
        if self.initial_state is None or self.alphabet is None:
            raise RuntimeError("DFA not loaded. Call load() successfully first.")

        visited = set()
        q = queue.Queue()
        q.put((self.initial_state, ""))

        while not q.empty():
            state, path = q.get()
            if state in visited:
                continue
            visited.add(state)

            if state.accepting == accepted:
                return path

            for symbol, dest in state.transition.items():
                q.put((dest, path + symbol))

        return None

if __name__ == "__main__":

    dfa = DFA()
    print(dfa.load("dfa.yaml"))
    print(dfa.accepts("1000"))
    print(dfa.accepts("1001"))

    inv = ~(~dfa)

    diff = dfa ^ inv
    print(diff.get_example() is not None)