from algo_hands_on.curriculum import MODULES, get_module, next_module_id


def test_curriculum_has_17_modules() -> None:
    assert [module.id for module in MODULES] == list(range(17))
    assert get_module(6).slug == "textos-colecoes"
    assert next_module_id(16) is None
