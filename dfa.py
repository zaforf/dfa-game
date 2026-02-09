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
        self.states = {}
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
    
    def minimize(self) -> int:
        # returns the number of states in the minimized DFA
        if self.initial_state is None or self.alphabet is None:
            raise RuntimeError("DFA not loaded. Call load() successfully first.")

        partition = [set(), set()]
        for state in self.states.values():
            if state.accepting: partition[0].add(state)
            else:               partition[1].add(state)
        
        if len(partition[0]) == 0 or len(partition[1]) == 0:
            return 1
        
        reverse = {}
        for state in self.states.values():
            for symbol, dest in state.transition.items():
                if (dest, symbol) not in reverse:
                    reverse[(dest, symbol)] = set()
                reverse[(dest, symbol)].add(state)

        group_map = {state: 0 if state.accepting else 1 for state in self.states.values()}
        splitters = {0 if len(partition[0]) < len(partition[1]) else 1}
        
        while splitters:
            splitter_id = splitters.pop()
            splitter = partition[splitter_id]

            for symbol in self.alphabet:
                # find states that transition to splitter on symbol
                X = set()
                for state in splitter:
                    if (state, symbol) in reverse:
                        X.update(reverse[(state, symbol)])
                if not X: continue

                # group states in X by their current partition
                impacted = {}
                for state in X:
                    group_id = group_map[state]
                    if group_id not in impacted:
                        impacted[group_id] = set()
                    impacted[group_id].add(state)

                for group_id, intersect in impacted.items():
                    if len(intersect) < len(partition[group_id]):
                        
                        # split group_id into intersect and the rest
                        diff = partition[group_id] - intersect
                        partition[group_id] = intersect
                        new_group_id = len(partition)
                        partition.append(diff)

                        for state in diff:
                            group_map[state] = new_group_id

                        if group_id in splitters:
                            # group_id is already a splitter, so add the new group as a splitter too
                            splitters.add(new_group_id)
                        else:
                            # add the smaller of the two groups as a splitter
                            splitters.add(group_id if len(intersect) < len(diff) else new_group_id)

        return len(partition)

        

if __name__ == "__main__":

    dfa = DFA()

    import json
    with open("challenges.json", "r") as f:
        challenges = json.load(f)
    
    for challenge in challenges:
        solution_path = challenge.get("solution")
        
        result = dfa.load(f"solutions/{solution_path}")
        if not result["success"]:
            print(f"Failed to load DFA for challenge {challenge['name']}: {result['errors']}")
            continue
        
        minimized_count = dfa.minimize()
        challenge["minimized_states"] = minimized_count
        print(f"Challenge {challenge['name']} has {minimized_count} states in the minimized DFA.")
        
    with open("challenges.json", "w") as f:
        json.dump(challenges, f, indent=2)
