from pathlib import Path
import runpy

# Allow `streamlit run app.py` from project root by delegating to frontend app.
runpy.run_path(str(Path(__file__).parent / "frontend" / "app.py"), run_name="__main__")
