from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dfa import DFA

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DFARequest(BaseModel):
    yaml_def: str
    test_string: str

@app.post("/check")
def check_on_dfa(request: DFARequest):
    try:
        dfa = DFA()
        load_result = dfa.load(request.yaml_def, is_file=False)
        if not load_result["success"]:
            return load_result

        result = dfa.accepts(request.test_string)
        return result
    
    except Exception as e:
        return {
            "success": False,
            "errors": [f"Server error: {str(e)}"]
        }
    
class DFASubmitRequest(BaseModel):
    yaml_def: str
    challenge: str
    solution: str

@app.post("/submit")
def submit_dfa_solution(request: DFASubmitRequest):
    try:
        dfa = DFA()
        load_result = dfa.load(request.yaml_def, is_file=False)
        if not load_result["success"]:
            return load_result

        solution = DFA()
        solution_load_result = solution.load("solutions/"+request.solution)
        if not solution_load_result["success"]:
            return {
                "success": False,
                "errors": [f"Error loading solution: {solution_load_result['errors']}"]
            }
        
        compare = dfa ^ solution
        example = compare.get_example()

        return {
            "success": example is None,
            "example": example
        }

    
    except Exception as e:
        return {
            "success": False,
            "errors": [f"Server error: {str(e)}"]
        }


app.mount("/", StaticFiles(directory=".", html=True), name="static")
