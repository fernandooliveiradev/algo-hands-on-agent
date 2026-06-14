from pathlib import Path

from agno.skills import LocalSkills, Skills


def test_all_skills_are_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    Skills(loaders=[LocalSkills(str(root / "skills"))])
