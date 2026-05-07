from app.util.courses import slug_to_display_name, courses_to_display_string, COURSE_DISPLAY_NAMES


def test_slug_to_display_name_known():
    assert slug_to_display_name("lakeview") == COURSE_DISPLAY_NAMES["lakeview"]
    assert slug_to_display_name("lakeview") == "Lakeview Golf Course"


def test_slug_to_display_name_unknown_hyphen():
    assert slug_to_display_name("unknown-course") == "Unknown Course"


def test_slug_to_display_name_unknown_underscore():
    assert slug_to_display_name("tpc_toronto") == "Tpc Toronto"


def test_courses_to_display_string_empty():
    assert courses_to_display_string([]) == "your alert"


def test_courses_to_display_string_single():
    result = courses_to_display_string(["lakeview"])
    assert result == "Lakeview Golf Course"


def test_courses_to_display_string_single_unknown():
    result = courses_to_display_string(["some-new-course"])
    assert result == "Some New Course"


def test_courses_to_display_string_multiple():
    result = courses_to_display_string(["lakeview", "braeben", "winchester"])
    assert result == "3 courses you're watching"


def test_courses_to_display_string_two():
    result = courses_to_display_string(["lakeview", "braeben"])
    assert result == "2 courses you're watching"


def test_all_known_slugs_have_display_names():
    for slug, name in COURSE_DISPLAY_NAMES.items():
        assert name, f"Empty display name for slug: {slug}"
        assert slug_to_display_name(slug) == name
