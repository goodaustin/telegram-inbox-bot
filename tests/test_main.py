def test_main_module_imports():
    from inbox_bot import main
    assert callable(main.main)
