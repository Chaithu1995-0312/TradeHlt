import sys
from pathlib import Path

# Add src/ to sys.path so all packages resolve without a 'src.' prefix
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
