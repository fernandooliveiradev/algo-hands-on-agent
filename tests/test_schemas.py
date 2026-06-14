from algo_hands_on.schemas import TutorTurn


def test_tutor_turn_normalizes_competency() -> None:
    turn = TutorTurn(message_markdown="Continue.", module_id=1, competency_key="Teste De Mesa")
    assert turn.competency_key == "teste-de-mesa"
